import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import torchvision.transforms as transforms
from torch.utils.data import Dataset, DataLoader
from PIL import Image
import numpy as np
import os
import random
from sklearn.metrics import classification_report, confusion_matrix


class SiameseDataset(Dataset):
    """Dataset for Siamese network training"""

    def __init__(self, logo_folder, text_folder, transform=None):
        self.transform = transform
        self.logo_images = []
        self.text_images = []

        # Load logo images
        for filename in os.listdir(logo_folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                self.logo_images.append(os.path.join(logo_folder, filename))

        # Load text images
        for filename in os.listdir(text_folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                self.text_images.append(os.path.join(text_folder, filename))

        print(f"Loaded {len(self.logo_images)} logos and {len(self.text_images)} text images")

    def __len__(self):
        # Return number of possible pairs
        return len(self.logo_images) * 4  # 4 pairs per logo image

    def __getitem__(self, idx):
        # Create positive and negative pairs

        if idx % 2 == 0:
            # Positive pair (logo-logo)
            img1_path = random.choice(self.logo_images)
            img2_path = random.choice(self.logo_images)
            label = 1.0
        else:
            # Negative pair (logo-text)
            img1_path = random.choice(self.logo_images)
            img2_path = random.choice(self.text_images)
            label = 0.0

        # Load images
        img1 = Image.open(img1_path).convert('RGB')
        img2 = Image.open(img2_path).convert('RGB')

        if self.transform:
            img1 = self.transform(img1)
            img2 = self.transform(img2)

        return img1, img2, torch.FloatTensor([label])


class SiameseNetwork(nn.Module):
    """Siamese network for logo detection"""

    def __init__(self, embedding_dim=128):
        super(SiameseNetwork, self).__init__()

        # Use pre-trained ResNet as backbone
        resnet = models.resnet50(pretrained=True)
        # Remove final layer
        self.backbone = nn.Sequential(*list(resnet.children())[:-1])

        # Add custom embedding layer
        self.embedding = nn.Sequential(
            nn.Linear(2048, 512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, embedding_dim),
        )

    def forward_one(self, x):
        """Forward pass for one branch"""
        x = self.backbone(x)
        x = x.view(x.size(0), -1)
        x = self.embedding(x)
        return x

    def forward(self, img1, img2):
        """Forward pass for both branches"""
        embedding1 = self.forward_one(img1)
        embedding2 = self.forward_one(img2)
        return embedding1, embedding2


class ContrastiveLoss(nn.Module):
    """Contrastive loss for Siamese network"""

    def __init__(self, margin=2.0):
        super(ContrastiveLoss, self).__init__()
        self.margin = margin

    def forward(self, output1, output2, label):
        euclidean_distance = F.pairwise_distance(output1, output2)
        loss_contrastive = torch.mean((1 - label) * torch.pow(euclidean_distance, 2) +
                                     (label) * torch.pow(torch.clamp(self.margin - euclidean_distance, min=0.0), 2))
        return loss_contrastive


class LogoSiameseDetector:
    """Logo detector using Siamese network"""

    def __init__(self, embedding_dim=128, device='cuda' if torch.cuda.is_available() else 'cpu'):
        self.device = device
        self.model = SiameseNetwork(embedding_dim).to(device)
        self.criterion = ContrastiveLoss()
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
        self.logo_embeddings = None
        self.logo_names = None

    def train(self, logo_folder, text_folder, epochs=50, batch_size=32, lr=0.0005):
        """Train the Siamese network"""

        # Create dataset and dataloader
        dataset = SiameseDataset(logo_folder, text_folder, self.transform)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # Optimizer
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)

        self.model.train()

        for epoch in range(epochs):
            running_loss = 0.0
            num_batches = 0

            for i, (img1, img2, labels) in enumerate(dataloader):
                img1, img2, labels = img1.to(self.device), img2.to(self.device), labels.to(self.device)

                optimizer.zero_grad()

                output1, output2 = self.model(img1, img2)
                loss = self.criterion(output1, output2, labels)

                loss.backward()
                optimizer.step()

                running_loss += loss.item()
                num_batches += 1

                if (i + 1) % 50 == 0:
                    print(f'Epoch [{epoch+1}/{epochs}], Step [{i+1}/{len(dataloader)}], Loss: {loss.item():.4f}')

            avg_loss = running_loss / num_batches
            print(f'Epoch [{epoch+1}/{epochs}], Average Loss: {avg_loss:.4f}')

            scheduler.step()

        print("Training completed!")

    def build_logo_database(self, logo_folder):
        """Build embedding database from logo images"""
        self.model.eval()

        logo_embeddings = []
        logo_names = []

        logo_files = [f for f in os.listdir(logo_folder)
                     if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]

        with torch.no_grad():
            for filename in logo_files:
                try:
                    filepath = os.path.join(logo_folder, filename)
                    img = Image.open(filepath).convert('RGB')
                    img_tensor = self.transform(img).unsqueeze(0).to(self.device)

                    embedding = self.model.forward_one(img_tensor)
                    logo_embeddings.append(embedding.cpu().numpy()[0])
                    logo_names.append(filename)

                except Exception as e:
                    print(f"Error processing {filename}: {e}")

        self.logo_embeddings = np.array(logo_embeddings)
        self.logo_names = logo_names
        print(f"Logo database built with {len(self.logo_embeddings)} embeddings")

    def detect_logo(self, image_path, threshold=1.0):
        """
        Detect if image is a logo using distance to logo embeddings

        Args:
            image_path: Path to test image
            threshold: Distance threshold (lower = more similar)
        """
        if self.logo_embeddings is None:
            raise ValueError("Logo database not built. Call build_logo_database() first.")

        self.model.eval()

        # Extract embedding for test image
        img = Image.open(image_path).convert('RGB')
        img_tensor = self.transform(img).unsqueeze(0).to(self.device)

        with torch.no_grad():
            test_embedding = self.model.forward_one(img_tensor).cpu().numpy()[0]

        # Compute distances to all logo embeddings
        distances = np.linalg.norm(self.logo_embeddings - test_embedding, axis=1)
        min_distance = np.min(distances)
        best_match_idx = np.argmin(distances)

        is_logo = min_distance < threshold
        best_match = self.logo_names[best_match_idx]

        return {
            'is_logo': is_logo,
            'min_distance': min_distance,
            'best_match': best_match,
            'all_distances': distances
        }

    def save_model(self, save_path):
        """Save trained model"""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'logo_embeddings': self.logo_embeddings,
            'logo_names': self.logo_names
        }, save_path)
        print(f"Model saved to {save_path}")

    def load_model(self, save_path):
        """Load trained model"""
        checkpoint = torch.load(save_path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.logo_embeddings = checkpoint.get('logo_embeddings')
        self.logo_names = checkpoint.get('logo_names')
        print(f"Model loaded from {save_path}")


def main(cfg):
    detector = LogoSiameseDetector()

    if cfg['train']==True:
        # Train the model (you need both logo and text folders)
        logo_folder = "all_processed"
        text_folder = "diverse_text_dataset_365"

        detector.train(logo_folder, text_folder, epochs=50)

        # Build logo database
        detector.build_logo_database(logo_folder)

        # Save model
        detector.save_model('siamese_logo_detector.pth')

    else:
        # Load pre-trained model and logo database
        detector.load_model('siamese_logo_detector.pth')
        # Test detection
        test_image = "images_processed/img_9.png"
        result = detector.detect_logo(test_image, threshold=0.018)

        print(f"Is Logo: {result['is_logo']}")
        print(f"Distance: {result['min_distance']:.3f}")
        print(f"Best Match: {result['best_match']}")

if __name__ == "__main__":
    cfg = {'train': False}
    main(cfg)
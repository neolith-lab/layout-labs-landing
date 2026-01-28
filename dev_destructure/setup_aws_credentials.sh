#!/bin/bash

# AWS Credentials Setup Script
# This script helps you set up AWS credentials for S3 uploads

echo "=========================================="
echo "AWS Credentials Setup for S3 Uploads"
echo "=========================================="
echo ""

# Check if credentials are already set
if [ ! -z "$AWS_ACCESS_KEY_ID" ] && [ ! -z "$AWS_SECRET_ACCESS_KEY" ] && [ ! -z "$AWS_REGION" ]; then
    echo "✅ AWS credentials are already set!"
    echo "   Access Key: ${AWS_ACCESS_KEY_ID:0:4}...${AWS_ACCESS_KEY_ID: -4}"
    echo "   Region: $AWS_REGION"
    echo ""
    read -p "Do you want to update them? (y/N): " update
    if [[ ! $update =~ ^[Yy]$ ]]; then
        echo "Keeping existing credentials."
        exit 0
    fi
    echo ""
fi

# Prompt for credentials
echo "Please enter your AWS credentials:"
echo ""

read -p "AWS Access Key ID: " access_key
read -sp "AWS Secret Access Key: " secret_key
echo ""
read -p "AWS Region (default: ap-south-1): " region
region=${region:-ap-south-1}

echo ""
echo "=========================================="
echo "Setting up credentials..."
echo "=========================================="

# Export for current session
export AWS_ACCESS_KEY_ID="$access_key"
export AWS_SECRET_ACCESS_KEY="$secret_key"
export AWS_REGION="$region"
export AWS_DEFAULT_REGION="$region"

# Create commands to add to shell profile
cat << EOF

✅ Credentials set for current terminal session!

To make these credentials permanent, add these lines to your ~/.zshrc:

export AWS_ACCESS_KEY_ID="$access_key"
export AWS_SECRET_ACCESS_KEY="$secret_key"
export AWS_REGION="$region"
export AWS_DEFAULT_REGION="$region"

Or run this command to add them automatically:

cat << 'CREDENTIALS' >> ~/.zshrc

# AWS Credentials for S3 uploads
export AWS_ACCESS_KEY_ID="$access_key"
export AWS_SECRET_ACCESS_KEY="$secret_key"
export AWS_REGION="$region"
export AWS_DEFAULT_REGION="$region"
CREDENTIALS

Then run: source ~/.zshrc

=========================================="
Testing S3 access to layoutlabs-temp...
=========================================="

EOF

# Test S3 access
if command -v aws &> /dev/null; then
    echo "Testing bucket access..."
    if aws s3 ls s3://layoutlabs-temp/ &> /dev/null; then
        echo "✅ Successfully connected to S3 bucket: layoutlabs-temp"
    else
        echo "⚠️  Could not access bucket layoutlabs-temp"
        echo "   Make sure the bucket exists and your credentials are correct"
    fi
else
    echo "⚠️  AWS CLI not found. Install it with: pip install awscli"
    echo "   Skipping bucket verification..."
fi

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "You can now run:"
echo "  python3 cli.py input.png -o output.svg --debug --s3-bucket layoutlabs-temp"
echo ""

import { motion } from "framer-motion";
import { FileText, Edit3, Zap, FolderSync } from "lucide-react";

const features = [
  {
    icon: FolderSync,
    title: "Smart Document Indexing",
    description: "Connect Drive, Dropbox, or upload directly. Our RAG engine understands your content contextually—not just keywords.",
  },
  {
    icon: Zap,
    title: "Instant Generation",
    description: "Describe what you need in natural language. Get polished infographics, reports, and presentations in seconds.",
  },
  {
    icon: Edit3,
    title: "Fully Editable Canvas",
    description: "Every element is selectable and movable. Text boxes, charts, shapes—edit anything like you would in Canva.",
  },
  {
    icon: FileText,
    title: "Multiple Formats",
    description: "Starting with infographics, expanding to reports, presentations, posters—any visual format you need.",
  },
];

export const FeaturesSection = () => {
  return (
    <section id="features" className="py-24 md:py-32">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-16 text-center"
        >
          <h2 className="mb-4 font-display text-3xl font-bold md:text-5xl">
            AI generation meets <span className="gradient-text">human control</span>
          </h2>
          <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
            No more manual file hunting. No more copy-paste formatting. 
            Get the speed of AI with the flexibility of professional design tools.
          </p>
        </motion.div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className="group"
            >
              <div className="glass-card h-full p-6 transition-all duration-300 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5">
                <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-110">
                  <feature.icon className="h-6 w-6" />
                </div>
                <h3 className="mb-2 font-display text-lg font-semibold">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.description}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

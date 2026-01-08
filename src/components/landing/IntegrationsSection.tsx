import { motion } from "framer-motion";
import { Cloud, HardDrive, Upload, Database } from "lucide-react";

const integrations = [
  { icon: HardDrive, name: "Google Drive", color: "text-yellow-500" },
  { icon: Cloud, name: "Dropbox", color: "text-blue-400" },
  { icon: Upload, name: "Direct Upload", color: "text-green-400" },
  { icon: Database, name: "More Coming", color: "text-purple-400" },
];

export const IntegrationsSection = () => {
  return (
    <section id="integrations" className="border-y border-border/50 bg-card/30 py-16">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <p className="mb-8 text-sm uppercase tracking-wider text-muted-foreground">
            Connect your favorite tools
          </p>

          <div className="flex flex-wrap items-center justify-center gap-8 md:gap-16">
            {integrations.map((integration, index) => (
              <motion.div
                key={integration.name}
                initial={{ opacity: 0, scale: 0.8 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: index * 0.1 }}
                className="flex flex-col items-center gap-2 text-muted-foreground transition-colors hover:text-foreground"
              >
                <integration.icon className={`h-10 w-10 ${integration.color}`} />
                <span className="text-sm font-medium">{integration.name}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
};

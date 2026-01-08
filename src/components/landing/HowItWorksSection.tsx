import { motion } from "framer-motion";

const steps = [
  {
    number: "01",
    title: "Connect Your Sources",
    description: "Link Google Drive, Dropbox, or upload files directly. Our AI indexes everything and understands context.",
  },
  {
    number: "02", 
    title: "Describe What You Need",
    description: '"Create an investor update with Q3 financials and project photos" — just tell us in plain English.',
  },
  {
    number: "03",
    title: "Edit & Export",
    description: "Get a fully editable canvas. Move elements, tweak text, adjust colors—then export in any format.",
  },
];

export const HowItWorksSection = () => {
  return (
    <section id="how-it-works" className="py-24 md:py-32">
      <div className="container mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-16 text-center"
        >
          <h2 className="mb-4 font-display text-3xl font-bold md:text-5xl">
            How it <span className="gradient-text">works</span>
          </h2>
          <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
            From scattered documents to professional visuals in three simple steps.
          </p>
        </motion.div>

        <div className="relative mx-auto max-w-4xl">
          {/* Connection line */}
          <div className="absolute left-8 top-0 hidden h-full w-px bg-gradient-to-b from-primary/50 via-purple-500/50 to-pink-500/50 md:left-1/2 md:block" />

          {steps.map((step, index) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, x: index % 2 === 0 ? -30 : 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.2 }}
              className={`relative mb-12 flex flex-col gap-6 md:flex-row md:items-center ${
                index % 2 === 1 ? "md:flex-row-reverse" : ""
              }`}
            >
              {/* Number bubble */}
              <div className="absolute left-0 flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-card font-display text-2xl font-bold text-primary md:relative md:left-auto">
                {step.number}
              </div>

              {/* Content */}
              <div className={`ml-24 md:ml-0 md:flex-1 ${index % 2 === 0 ? "md:pr-20" : "md:pl-20"}`}>
                <div className="glass-card p-6">
                  <h3 className="mb-2 font-display text-xl font-semibold">{step.title}</h3>
                  <p className="text-muted-foreground">{step.description}</p>
                </div>
              </div>

              {/* Spacer for alternating layout */}
              <div className="hidden md:block md:flex-1" />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

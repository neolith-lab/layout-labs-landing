import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ArrowRight, Sparkles } from "lucide-react";

export const HeroSection = () => {
  return (
    <section className="relative min-h-screen overflow-hidden pt-16">
      {/* Background effects */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute left-1/4 top-1/4 h-96 w-96 rounded-full bg-primary/10 blur-[120px] animate-pulse-glow" />
        <div className="absolute right-1/4 bottom-1/4 h-96 w-96 rounded-full bg-purple-500/10 blur-[120px] animate-pulse-glow animation-delay-200" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-pink-500/5 blur-[150px] animate-pulse-glow animation-delay-400" />
      </div>

      <div className="container mx-auto flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center px-4 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-4 py-1.5 text-sm backdrop-blur-sm"
        >
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-muted-foreground">Powered by your actual business documents</span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mb-6 max-w-4xl font-display text-4xl font-bold leading-tight tracking-tight md:text-6xl lg:text-7xl"
        >
          Transform scattered docs into{" "}
          <span className="gradient-text">stunning visuals</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mb-10 max-w-2xl text-lg text-muted-foreground md:text-xl"
        >
          Connect your Drive or Dropbox. Describe what you need. Get fully editable 
          infographics, reports, and presentations—generated instantly from your content.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="flex flex-col gap-4 sm:flex-row"
        >
          <Button variant="hero" size="xl">
            Start Creating Free
            <ArrowRight className="h-5 w-5" />
          </Button>
          <Button variant="heroOutline" size="xl">
            Watch Demo
          </Button>
        </motion.div>

        {/* Floating preview mockup */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.5 }}
          className="mt-16 w-full max-w-5xl"
        >
          <div className="glass-card p-2 md:p-4">
            <div className="aspect-video overflow-hidden rounded-lg bg-gradient-to-br from-secondary to-muted">
              <div className="flex h-full flex-col">
                {/* Mock toolbar */}
                <div className="flex items-center gap-2 border-b border-border/50 bg-card/50 px-4 py-2">
                  <div className="flex gap-1.5">
                    <div className="h-3 w-3 rounded-full bg-destructive/60" />
                    <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                    <div className="h-3 w-3 rounded-full bg-green-500/60" />
                  </div>
                  <div className="ml-4 flex-1 rounded-md bg-muted/50 px-3 py-1 text-xs text-muted-foreground">
                    "Create an investor update with Q3 financials..."
                  </div>
                </div>
                {/* Mock canvas */}
                <div className="flex-1 p-6">
                  <div className="grid h-full grid-cols-3 gap-4">
                    <div className="col-span-2 rounded-lg border border-primary/20 bg-card/30 p-4">
                      <div className="mb-3 h-4 w-32 rounded bg-foreground/10" />
                      <div className="mb-2 h-3 w-full rounded bg-foreground/5" />
                      <div className="mb-2 h-3 w-4/5 rounded bg-foreground/5" />
                      <div className="mb-4 h-3 w-3/5 rounded bg-foreground/5" />
                      <div className="h-24 rounded-lg bg-gradient-to-r from-primary/20 to-purple-500/20" />
                    </div>
                    <div className="space-y-4">
                      <div className="rounded-lg border border-border/50 bg-card/30 p-3">
                        <div className="mb-2 h-3 w-20 rounded bg-primary/30" />
                        <div className="text-2xl font-bold text-primary">$2.4M</div>
                      </div>
                      <div className="rounded-lg border border-border/50 bg-card/30 p-3">
                        <div className="mb-2 h-3 w-16 rounded bg-purple-500/30" />
                        <div className="text-2xl font-bold text-purple-400">+42%</div>
                      </div>
                      <div className="rounded-lg border border-border/50 bg-card/30 p-3">
                        <div className="mb-2 h-3 w-24 rounded bg-pink-500/30" />
                        <div className="text-2xl font-bold text-pink-400">128</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};

"use client";

import { AnimatedGradientText } from "@/components/ui/animated-gradient-text";
import { BentoCard, BentoGrid } from "@/components/ui/bento-grid";
import { CodeTabs } from "@/components/ui/code-tabs";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { motion, useInView } from "framer-motion";
import {
  Brain,
  GitBranch,
  Globe,
  Layers,
  MessageSquare,
  Sparkles,
  Zap,
  Code2,
  Server,
  ArrowRight,
} from "lucide-react";
import { useRef } from "react";

const BOOKING_URL = "https://calendar.superhuman.com/book/11SzDnK01g1VgPEI2w/FtV5Q";

const pythonCode = `<span class="token-keyword">from</span> memento_ai <span class="token-keyword">import</span> build_store, MemoryCreate

<span class="token-keyword">with</span> <span class="token-function">build_store</span>(<span class="token-string">"postgresql://..."</span>) <span class="token-keyword">as</span> store:
    <span class="token-comment"># Remember something</span>
    store.<span class="token-function">add</span>(namespace, <span class="token-function">MemoryCreate</span>(
        text=<span class="token-string">"User prefers dark mode"</span>,
        durability=<span class="token-string">"core"</span>,  <span class="token-comment"># Never forget</span>
    ))

    <span class="token-comment"># Recall it later</span>
    memories = store.<span class="token-function">search</span>(namespace, <span class="token-string">"user preferences"</span>)`;

const typescriptCode = `<span class="token-keyword">import</span> { MemoryStore, createOpenAIEmbeddings } <span class="token-keyword">from</span> <span class="token-string">'memento-ai'</span>;
<span class="token-keyword">import</span> { neon } <span class="token-keyword">from</span> <span class="token-string">'@neondatabase/serverless'</span>;

<span class="token-keyword">const</span> store = <span class="token-keyword">new</span> <span class="token-function">MemoryStore</span>(<span class="token-function">neon</span>(DATABASE_URL), embeddings);

<span class="token-comment">// Remember something</span>
<span class="token-keyword">await</span> store.<span class="token-function">add</span>(namespace, {
  text: <span class="token-string">"User prefers dark mode"</span>,
  durability: <span class="token-string">"core"</span>,
});

<span class="token-comment">// Recall it later</span>
<span class="token-keyword">const</span> memories = <span class="token-keyword">await</span> store.<span class="token-function">search</span>(namespace, <span class="token-string">"user preferences"</span>);`;

const mcpCode = `<span class="token-comment">// Zero-config: memories stored locally in ~/.memento/</span>
{
  <span class="token-string">"mcpServers"</span>: {
    <span class="token-string">"memento"</span>: {
      <span class="token-string">"command"</span>: <span class="token-string">"npx"</span>,
      <span class="token-string">"args"</span>: [<span class="token-string">"memento-mcp"</span>],
      <span class="token-string">"env"</span>: {
        <span class="token-string">"OPENAI_API_KEY"</span>: <span class="token-string">"sk-..."</span>
      }
    }
  }
}

<span class="token-comment">// Add DATABASE_URL for Postgres/cloud sync</span>
<span class="token-comment">// Tools: remember, recall, list_memories, forget</span>`;

// Animation variants
const fadeInUp = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0 },
};

const stagger = {
  visible: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};

function AnimatedSection({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });

  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={isInView ? "visible" : "hidden"}
      variants={stagger}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export default function Home() {
  return (
    <div className="min-h-screen bg-[var(--background)] transition-colors">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <span className="font-semibold text-lg text-[var(--foreground)]">
              memento<span className="text-purple-500">-ai</span>
            </span>
          </a>
          <div className="flex items-center gap-4">
            <a href="https://github.com/joelash/memento-ai" className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors text-sm hidden sm:block">
              GitHub
            </a>
            <a href="https://github.com/joelash/memento-ai#quick-start" className="text-[var(--muted)] hover:text-[var(--foreground)] transition-colors text-sm hidden sm:block">
              Docs
            </a>
            <ThemeToggle />
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-24 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[var(--border)] bg-[var(--surface)] text-sm text-[var(--muted)] mb-8">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span>Now with TypeScript + MCP support</span>
            </div>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-5xl md:text-7xl font-bold tracking-tight mb-6 text-[var(--foreground)]"
          >
            Your AI agents keep{" "}
            <AnimatedGradientText>forgetting</AnimatedGradientText>.
            <br />
            Let&apos;s fix that.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-xl text-[var(--muted)] mb-10 max-w-2xl mx-auto"
          >
            Production-grade semantic memory for AI agents. Works with Python, TypeScript, and any tool via MCP.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="flex flex-wrap items-center justify-center gap-4"
          >
            <ShimmerButton href="https://github.com/joelash/memento-ai">
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              Get Started
            </ShimmerButton>
            <a
              href="#features"
              className="px-6 py-3 rounded-lg border border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--surface)] transition-colors font-medium"
            >
              Learn More
            </a>
          </motion.div>
        </div>
      </section>

      {/* Code Examples */}
      <section className="py-24 px-6 border-t border-[var(--border)]">
        <AnimatedSection className="max-w-6xl mx-auto">
          <motion.div variants={fadeInUp} className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4 text-[var(--foreground)]">Works everywhere</h2>
            <p className="text-[var(--muted)]">Python, TypeScript, or any tool via MCP</p>
          </motion.div>

          <motion.div variants={fadeInUp}>
            <CodeTabs
              tabs={[
                {
                  label: "Python",
                  icon: <Code2 className="w-4 h-4" />,
                  code: pythonCode,
                },
                {
                  label: "TypeScript",
                  icon: <Server className="w-4 h-4" />,
                  code: typescriptCode,
                },
                {
                  label: "MCP",
                  icon: <MessageSquare className="w-4 h-4" />,
                  code: mcpCode,
                },
              ]}
            />
          </motion.div>

          {/* Platform badges */}
          <motion.div variants={fadeInUp} className="flex flex-wrap items-center justify-center gap-4 mt-10">
            {[
              { icon: Globe, label: "Cloudflare Workers" },
              { icon: Zap, label: "Neon Serverless" },
              { icon: Layers, label: "Vercel AI SDK" },
            ].map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--surface)] border border-[var(--border)] text-sm text-[var(--muted)]">
                <Icon className="w-4 h-4" />
                {label}
              </div>
            ))}
          </motion.div>
        </AnimatedSection>
      </section>

      {/* Features Bento Grid */}
      <section id="features" className="py-24 px-6 border-t border-[var(--border)]">
        <AnimatedSection className="max-w-6xl mx-auto">
          <motion.div variants={fadeInUp} className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4 text-[var(--foreground)]">Built for production</h2>
            <p className="text-[var(--muted)]">Not another demo. Actually works.</p>
          </motion.div>

          <BentoGrid>
            <BentoCard
              icon={<GitBranch className="w-6 h-6" />}
              title="Version Chains"
              description="When facts change, we create an audit trail. Debug why your agent thinks what it thinks."
              className="lg:col-span-2"
            />
            <BentoCard
              icon={<Layers className="w-6 h-6" />}
              title="Durability Tiers"
              description="Core facts (forever), situational context (temporary), episodic memories (decay over time)."
            />
            <BentoCard
              icon={<Globe className="w-6 h-6" />}
              title="Multi-Backend"
              description="Postgres for production, SQLite for dev, DuckDB for analytics. No vendor lock-in."
            />
            <BentoCard
              icon={<Brain className="w-6 h-6" />}
              title="Memory Types"
              description="Facts, rules, decisions, preferences, observations. Structured semantics for smart retrieval."
            />
            <BentoCard
              icon={<Zap className="w-6 h-6" />}
              title="Edge-Ready"
              description="TypeScript client works with Neon serverless on Cloudflare Workers. Sub-100ms latency."
            />
          </BentoGrid>
        </AnimatedSection>
      </section>

      {/* MCP Section */}
      <section className="py-24 px-6 border-t border-[var(--border)]">
        <AnimatedSection className="max-w-4xl mx-auto text-center">
          <motion.div variants={fadeInUp}>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-purple-500/30 bg-purple-500/10 text-sm text-purple-400 mb-8">
              <MessageSquare className="w-4 h-4" />
              MCP Server Included
            </div>
          </motion.div>
          <motion.h2 variants={fadeInUp} className="text-3xl font-bold mb-4 text-[var(--foreground)]">
            Memory for any tool
          </motion.h2>
          <motion.p variants={fadeInUp} className="text-[var(--muted)] mb-10 max-w-2xl mx-auto">
            The included MCP server lets Claude Desktop, Cursor, and other tools remember things across sessions. No code changes needed.
          </motion.p>

          <motion.div variants={fadeInUp} className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-2xl mx-auto">
            {["remember", "recall", "list_memories", "forget"].map((tool) => (
              <div
                key={tool}
                className="px-4 py-3 rounded-lg bg-[var(--surface)] border border-[var(--border)] font-mono text-sm text-purple-400"
              >
                {tool}
              </div>
            ))}
          </motion.div>

          {/* Hosted option CTA */}
          <motion.div 
            variants={fadeInUp} 
            className="mt-12 p-6 rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface)]/50 max-w-lg mx-auto"
          >
            <p className="text-[var(--muted)] text-sm mb-3">
              Don&apos;t want to manage your own database?
            </p>
            <a
              href="mailto:joel@friedman.xyz?subject=Interested%20in%20hosted%20memento-ai&body=I%27m%20interested%20in%20a%20hosted%20version%20of%20memento-ai.%0A%0AMy%20use%20case%3A%20"
              className="inline-flex items-center gap-2 text-purple-400 hover:text-purple-300 text-sm font-medium transition-colors"
            >
              Interested in a hosted option? Let me know <ArrowRight className="w-4 h-4" />
            </a>
          </motion.div>
        </AnimatedSection>
      </section>

      {/* Footer */}
      <footer className="py-16 px-6 border-t border-[var(--border)]">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-12 mb-12">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <Brain className="w-5 h-5 text-white" />
                </div>
                <span className="font-semibold text-lg text-[var(--foreground)]">
                  memento<span className="text-purple-500">-ai</span>
                </span>
              </div>
              <p className="text-[var(--muted)] text-sm max-w-md">
                Open source semantic memory for AI agents. MIT licensed.
              </p>
            </div>
            <div className="md:text-right">
              <h3 className="font-semibold mb-4 text-[var(--foreground)]">Need help implementing?</h3>
              <p className="text-[var(--muted)] text-sm mb-4">
                I&apos;ll add production-grade memory to your AI agent.
              </p>
              <a
                href={BOOKING_URL}
                className="inline-flex items-center gap-2 text-purple-400 hover:text-purple-300 text-sm font-medium transition-colors"
              >
                Book a call <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          </div>
          <div className="pt-8 border-t border-[var(--border)] text-center text-sm text-[var(--muted)]">
            Built by{" "}
            <a href="https://twitter.com/joelash" className="hover:text-[var(--foreground)] transition-colors">
              @joelash
            </a>{" "}
            ·{" "}
            <a href="https://github.com/joelash/memento-ai" className="hover:text-[var(--foreground)] transition-colors">
              GitHub
            </a>{" "}
            · MIT License
          </div>
        </div>
      </footer>
    </div>
  );
}

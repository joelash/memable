"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface ShimmerButtonProps {
  children: React.ReactNode;
  className?: string;
  href?: string;
}

export function ShimmerButton({ children, className, href }: ShimmerButtonProps) {
  const Comp = href ? "a" : "button";
  
  return (
    <Comp
      href={href}
      className={cn(
        "group relative inline-flex items-center justify-center overflow-hidden rounded-lg bg-orange-500 px-6 py-3 font-medium text-white transition-all hover:bg-orange-600",
        className
      )}
    >
      <span className="relative z-10 flex items-center gap-2">{children}</span>
      <motion.div
        className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
        animate={{
          x: ["-100%", "100%"],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "linear",
        }}
      />
    </Comp>
  );
}

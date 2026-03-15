"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface AnimatedGradientTextProps {
  children: React.ReactNode;
  className?: string;
}

export function AnimatedGradientText({
  children,
  className,
}: AnimatedGradientTextProps) {
  return (
    <motion.span
      className={cn(
        "bg-gradient-to-r from-orange-500 via-amber-400 to-orange-500 bg-[length:200%_auto] bg-clip-text text-transparent",
        className
      )}
      animate={{
        backgroundPosition: ["0%", "200%"],
      }}
      transition={{
        duration: 3,
        repeat: Infinity,
        ease: "linear",
      }}
    >
      {children}
    </motion.span>
  );
}

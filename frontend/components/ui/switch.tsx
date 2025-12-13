"use client"

import * as React from "react"
import * as SwitchPrimitives from "@radix-ui/react-switch"
import { motion } from "framer-motion"

import { cn } from "@/utils/cn"

const Switch = React.forwardRef<
    React.ElementRef<typeof SwitchPrimitives.Root>,
    React.ComponentPropsWithoutRef<typeof SwitchPrimitives.Root>
>(({ className, ...props }, ref) => (
    <SwitchPrimitives.Root
        className={cn(
            "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input",
            className
        )}
        {...props}
        ref={ref}
    >
        <SwitchPrimitives.Thumb
            className={cn(
                "pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0"
            )}
        />
    </SwitchPrimitives.Root>
))
Switch.displayName = SwitchPrimitives.Root.displayName

// Animated Toggle with Icons (for theme toggle)
interface AnimatedToggleProps {
    checked: boolean
    onCheckedChange: (checked: boolean) => void
    leftIcon: React.ReactNode
    rightIcon: React.ReactNode
    className?: string
}

const AnimatedToggle = React.forwardRef<HTMLButtonElement, AnimatedToggleProps>(
    ({ checked, onCheckedChange, leftIcon, rightIcon, className }, ref) => (
        <button
            ref={ref}
            onClick={() => onCheckedChange(!checked)}
            className={cn(
                "relative flex h-9 w-[68px] items-center rounded-full bg-muted p-1 cursor-pointer transition-colors hover:bg-muted/80",
                className
            )}
        >
            {/* Background slider - same size as icon containers */}
            <motion.div
                className="absolute h-7 w-7 rounded-full bg-primary shadow-md"
                style={{ left: 4 }}
                animate={{ x: checked ? 28 : 0 }}
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
            />
            {/* Icons - fixed width containers for symmetry */}
            <div className="relative z-10 flex w-full">
                <span className={cn(
                    "flex h-7 w-7 items-center justify-center transition-colors duration-200",
                    !checked ? "text-primary-foreground" : "text-muted-foreground"
                )}>
                    {leftIcon}
                </span>
                <span className={cn(
                    "flex h-7 w-7 items-center justify-center transition-colors duration-200",
                    checked ? "text-primary-foreground" : "text-muted-foreground"
                )}>
                    {rightIcon}
                </span>
            </div>
        </button>
    )
)
AnimatedToggle.displayName = "AnimatedToggle"

// Segmented Toggle for SOP/HS Code selection
interface SegmentedToggleProps {
    value: string
    onValueChange: (value: string) => void
    options: { value: string; label: string; tooltip?: string }[]
    className?: string
}

const SegmentedToggle = React.forwardRef<HTMLDivElement, SegmentedToggleProps>(
    ({ value, onValueChange, options, className }, ref) => (
        <div
            ref={ref}
            className={cn(
                "relative flex h-9 items-center rounded-lg bg-muted p-1",
                className
            )}
        >
            {/* Animated background */}
            <motion.div
                className="absolute h-7 rounded-md bg-background shadow-sm"
                style={{ width: `calc(${100 / options.length}% - 4px)` }}
                animate={{
                    x: options.findIndex(o => o.value === value) * (100 / options.length) + '%'
                }}
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
            />
            {/* Options */}
            {options.map((option) => (
                <button
                    key={option.value}
                    onClick={() => onValueChange(option.value)}
                    className={cn(
                        "relative z-10 flex-1 px-3 py-1 text-sm font-medium transition-colors cursor-pointer rounded-md",
                        value === option.value
                            ? "text-foreground"
                            : "text-muted-foreground hover:text-foreground"
                    )}
                >
                    {option.label}
                </button>
            ))}
        </div>
    )
)
SegmentedToggle.displayName = "SegmentedToggle"

export { Switch, AnimatedToggle, SegmentedToggle }

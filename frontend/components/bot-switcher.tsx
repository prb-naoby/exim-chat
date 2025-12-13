"use strict";
import * as React from "react"
import { motion } from "framer-motion"
import { cn } from "@/utils/cn"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

import { useRouter } from "next/navigation"

interface BotSwitcherProps {
    chatbotType: 'SOP' | 'INSW' | 'OTHERS';
    setChatbotType: (type: 'SOP' | 'INSW' | 'OTHERS') => void;
}

export function BotSwitcher({ chatbotType, setChatbotType }: BotSwitcherProps) {
    const router = useRouter();

    const handleSwitch = (type: 'SOP' | 'INSW' | 'OTHERS') => {
        // Optimistically update state
        setChatbotType(type);
        // Navigate to the respective page
        if (type === 'SOP') {
            router.push('/sop');
        } else if (type === 'INSW') {
            router.push('/insw');
        } else {
            router.push('/others');
        }
    };

    return (
        <TooltipProvider delayDuration={300}>
            <div className="px-2 pb-2 group-data-[collapsible=icon]:hidden">
                <div className="relative flex h-10 items-center rounded-lg bg-muted p-1">
                    <motion.div
                        layout
                        transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                        className={cn(
                            "absolute h-8 rounded-md bg-background shadow-sm",
                            chatbotType === 'SOP' ? "left-1 right-2/3" :
                                chatbotType === 'INSW' ? "left-[33.33%] right-[33.33%]" :
                                    "left-2/3 right-1"
                        )}
                    />
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => handleSwitch('SOP')}
                                className={cn(
                                    "z-10 w-1/3 text-sm font-medium transition-colors cursor-pointer focus:outline-none",
                                    chatbotType === 'SOP' ? "text-foreground" : "text-muted-foreground hover:text-foreground/80"
                                )}
                                type="button"
                            >
                                SOP
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Standard Operating Procedure</p>
                        </TooltipContent>
                    </Tooltip>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => handleSwitch('INSW')}
                                className={cn(
                                    "z-10 w-1/3 text-sm font-medium transition-colors cursor-pointer focus:outline-none",
                                    chatbotType === 'INSW' ? "text-foreground" : "text-muted-foreground hover:text-foreground/80"
                                )}
                                type="button"
                            >
                                HS Code
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Harmonized System Code</p>
                        </TooltipContent>
                    </Tooltip>
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button
                                onClick={() => handleSwitch('OTHERS')}
                                className={cn(
                                    "z-10 w-1/3 text-sm font-medium transition-colors cursor-pointer focus:outline-none",
                                    chatbotType === 'OTHERS' ? "text-foreground" : "text-muted-foreground hover:text-foreground/80"
                                )}
                                type="button"
                            >
                                General
                            </button>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>General EXIM & Internal Info</p>
                        </TooltipContent>
                    </Tooltip>
                </div>
            </div>
        </TooltipProvider>
    )
}


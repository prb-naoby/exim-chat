'use client';

import { MessageSquare } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { fetchAPI } from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export default function SOPPage() {
    const router = useRouter();

    const handleNewChat = async () => {
        try {
            const res = await fetchAPI('/chat/sessions', {
                method: 'POST',
                body: JSON.stringify({ chatbot_type: 'SOP', title: 'New Chat' })
            });
            if (res.ok) {
                const data = await res.json();
                router.push(`/sop/${data.session_id}`);
            }
        } catch (e) {
            console.error("Error creating chat", e);
        }
    };

    return (
        <TooltipProvider delayDuration={300}>
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-8 text-center">
                <motion.div
                    initial={{ scale: 0.9, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ type: "spring", stiffness: 300, damping: 20 }}
                    className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mb-4"
                >
                    <MessageSquare size={32} className="text-foreground" />
                </motion.div>
                <motion.div
                    initial={{ y: 10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.1 }}
                >
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <h3 className="text-xl font-semibold text-foreground mb-2 cursor-default">
                                SOP Assistant
                            </h3>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Standard Operation Procedure</p>
                        </TooltipContent>
                    </Tooltip>
                </motion.div>
                <motion.p
                    initial={{ y: 10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.2 }}
                    className="max-w-md mb-6"
                >
                    Ask questions about Standard Operating Procedures, EXIM regulations, and compliance guidelines.
                </motion.p>
                <motion.div
                    initial={{ y: 10, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ delay: 0.3 }}
                >
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button onClick={handleNewChat}>
                                Start New Chat
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                            <p>Create a new conversation</p>
                        </TooltipContent>
                    </Tooltip>
                </motion.div>
            </div>
        </TooltipProvider>
    );
}

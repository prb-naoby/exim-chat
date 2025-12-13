'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
// import { motion, AnimatePresence } from 'framer-motion'; // Removed unused
import { ChatInterface } from '@/components/ChatInterface';
import { fetchAPI, getCurrentUser } from '@/utils/api';
import { MessageSquare } from 'lucide-react'; // Removed unused icons
import { Button } from '@/components/ui/button';
import { ModeToggle } from '@/components/mode-toggle'; // Actually used in AppSidebar, but here? Only in mobile header before?
// In new layout, ModeToggle is in AppSidebar. 
// Check if used in "Main Content" header? No, I removed it from header in replaced content.
// Wait, I kept it in "header ... sticky top-0". Let's check line 133 replacement.
// Only SidebarTrigger and title are there.
// So ModeToggle is unused in page.tsx if it's only in AppSidebar.

import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar"
import { AppSidebar } from "@/components/app-sidebar"

export default function DashboardPage() {
    const router = useRouter();
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const [user, setUser] = useState<any>(null);
    const [chatbotType, setChatbotType] = useState<'SOP' | 'INSW'>('SOP');
    // const [sidebarOpen, setSidebarOpen] = useState(true); // Managed by SidebarProvider
    const [sessions, setSessions] = useState<any[]>([]);
    const [currentSessionId, setCurrentSessionId] = useState<string>('');
    const [messages, setMessages] = useState<any[]>([]);
    /* eslint-enable @typescript-eslint/no-explicit-any */

    // Auth Check
    useEffect(() => {
        const currentUser = getCurrentUser();
        if (!currentUser) {
            router.push('/login');
        } else {
            setUser(currentUser);
        }
    }, [router]);

    // Load Sessions when type changes
    useEffect(() => {
        loadSessions();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [chatbotType]);

    const loadSessions = async () => {
        try {
            const res = await fetchAPI(`/chat/sessions/${chatbotType}`);
            if (res.ok) {
                const data = await res.json();
                setSessions(data);
            }
        } catch (error) {
            console.error('Error loading sessions:', error);
        }
    };

    // Load History when session changes
    useEffect(() => {
        if (!currentSessionId) {
            setMessages([]);
            return;
        }
        loadHistory(currentSessionId);
    }, [currentSessionId]);

    const loadHistory = async (sessionId: string) => {
        try {
            const res = await fetchAPI(`/chat/history/${sessionId}`);
            if (res.ok) {
                const data = await res.json();
                setMessages(data);
            }
        } catch (e) {
            console.error("Error loading history", e);
        }
    };

    const handleNewChat = async () => {
        const title = "New Chat";
        try {
            const res = await fetchAPI('/chat/sessions', {
                method: 'POST',
                body: JSON.stringify({ chatbot_type: chatbotType, title })
            });
            if (res.ok) {
                const data = await res.json();
                const newSessionId = data.session_id;
                await loadSessions();
                setCurrentSessionId(newSessionId);
            }
        } catch (e) {
            console.error("Error creating chat", e);
        }
    };

    const handleDeleteSession = async (id: string) => {
        try {
            await fetchAPI(`/chat/history/${id}`, { method: 'DELETE' });
            if (currentSessionId === id) setCurrentSessionId('');
            loadSessions();
        } catch (e) {
            console.error("Error deleting session", e);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
    };

    const handleSelectSession = (id: string) => {
        setCurrentSessionId(id);
        // Sidebar auto-collapses on mobile via Sheet primitive in Shadcn, 
        // but we might want to close explicitly if using custom logic. 
        // AppSidebar handles `setOpenMobile(false)` on click.
    };

    if (!user) return null;

    return (
        <TooltipProvider delayDuration={300}>
            <SidebarProvider>
                <AppSidebar
                    sessions={sessions}
                    currentSessionId={currentSessionId}
                    onSelectSession={handleSelectSession}
                    onNewChat={handleNewChat}
                    onDeleteSession={handleDeleteSession}
                    chatbotType={chatbotType}
                    setChatbotType={setChatbotType}
                    user={user}
                    handleLogout={handleLogout}
                    onRefreshSessions={loadSessions}
                />
                <SidebarInset>
                    <div className="flex flex-col h-full overflow-hidden">
                        {/* Header */}
                        <header className="flex h-16 shrink-0 items-center gap-2 px-4 sticky top-0 bg-background z-10 transition-[width,height] ease-linear group-has-[[data-collapsible=icon]]/sidebar-wrapper:h-12">
                            <div className="flex items-center gap-2 px-4">
                                <SidebarTrigger className="-ml-1" />
                                <span className="font-semibold">{chatbotType === 'SOP' ? 'SOP' : 'HS Code'} Assistant</span>
                            </div>
                            <div className="ml-auto flex items-center gap-2">
                                {/* Extra header items if any */}
                            </div>
                        </header>

                        <main className="flex-1 overflow-hidden relative">
                            {currentSessionId ? (
                                <ChatInterface
                                    chatbotType={chatbotType}
                                    sessionId={currentSessionId}
                                    initialMessages={messages}
                                    onMessageSent={() => loadSessions()}
                                />
                            ) : (
                                <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-8 text-center">
                                    <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mb-4">
                                        <MessageSquare size={32} />
                                    </div>
                                    <h3 className="text-xl font-semibold text-foreground mb-2">
                                        Welcome, {user.display_name || user.username}!
                                    </h3>
                                    <p className="max-w-md">
                                        Select a chat from the sidebar or start a new conversation.
                                    </p>
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Button onClick={handleNewChat} className="mt-6">
                                                Start New Chat
                                            </Button>
                                        </TooltipTrigger>
                                        <TooltipContent><p>Create a new conversation</p></TooltipContent>
                                    </Tooltip>
                                </div>
                            )}
                        </main>
                    </div>
                </SidebarInset>
            </SidebarProvider>
        </TooltipProvider>
    );
}

'use client';

import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { AppSidebar } from '@/components/app-sidebar';
import { fetchAPI, getCurrentUser } from '@/utils/api';
import { SidebarProvider, SidebarTrigger, SidebarInset } from '@/components/ui/sidebar';
import { ModeToggle } from '@/components/mode-toggle';
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';

export default function ChatLayout({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const pathname = usePathname();
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const [user, setUser] = useState<any>(null);
    const [sessions, setSessions] = useState<any[]>([]);
    const [chatbotType, setChatbotType] = useState<'SOP' | 'INSW' | 'OTHERS'>('SOP');
    /* eslint-enable @typescript-eslint/no-explicit-any */

    // Sync chatbot type with URL
    useEffect(() => {
        if (pathname.startsWith('/insw')) {
            setChatbotType('INSW');
        } else if (pathname.startsWith('/others')) {
            setChatbotType('OTHERS');
        } else {
            setChatbotType('SOP');
        }
    }, [pathname]);

    // Extract current session ID
    const pathParts = pathname.split('/');
    const currentSessionId = pathParts.length > 2 ? pathParts[2] : '';

    // Auth Check
    useEffect(() => {
        const currentUser = getCurrentUser();
        if (!currentUser) {
            router.push('/login');
        } else {
            setUser(currentUser);
        }
    }, [router]);

    // Load Sessions
    useEffect(() => {
        if (user) {
            loadSessions();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [chatbotType, user]);

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

    // Background refresh: silently reload sessions every 30 seconds
    useEffect(() => {
        if (!user) return;

        const backgroundRefresh = setInterval(async () => {
            try {
                const res = await fetchAPI(`/chat/sessions/${chatbotType}`);
                if (res.ok) {
                    const data = await res.json();
                    // Only update if data changed to avoid unnecessary re-renders
                    setSessions(prev => {
                        const prevIds = prev.map(s => s.session_id).join(',');
                        const newIds = data.map((s: any) => s.session_id).join(','); // eslint-disable-line @typescript-eslint/no-explicit-any
                        return prevIds !== newIds ? data : prev;
                    });
                }
            } catch (error) {
                // Silently fail for background refresh
                console.debug('Background refresh failed:', error);
            }
        }, 30000); // 30 seconds

        return () => clearInterval(backgroundRefresh);
    }, [user, chatbotType]);

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
                router.push(`/${chatbotType.toLowerCase()}/${newSessionId}`);
            }
        } catch (e) {
            console.error("Error creating chat", e);
        }
    };

    const handleSelectSession = (id: string) => {
        router.push(`/${chatbotType.toLowerCase()}/${id}`);
    };

    const handleDeleteSession = async (id: string) => {
        try {
            await fetchAPI(`/chat/history/${id}`, { method: 'DELETE' });
            if (currentSessionId === id || !currentSessionId) {
                // stay on same page but clear ID if needed, or redirect
                if (currentSessionId === id) router.push(`/${chatbotType.toLowerCase()}`);
            }
            loadSessions();
        } catch (e) {
            console.error("Error deleting session", e);
        }
    };

    const handleDeleteAllSessions = async () => {
        try {
            const res = await fetchAPI(`/chat/sessions/${chatbotType}`, { method: 'DELETE' });
            if (res.ok) {
                router.push(`/${chatbotType.toLowerCase()}`);
                await loadSessions();
                setSessions([]);
            }
        } catch (e) {
            console.error("Error deleting all sessions", e);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        router.push('/login');
    };

    const handleChatbotTypeChange = (type: 'SOP' | 'INSW' | 'OTHERS') => {
        if (type !== chatbotType) {
            router.push(`/${type.toLowerCase()}`);
        }
    };

    if (!user) return null;

    return (
        <TooltipProvider delayDuration={300}>
            <SidebarProvider defaultOpen={true}>
                <AppSidebar
                    user={user}
                    sessions={sessions}
                    currentSessionId={currentSessionId}
                    onSelectSession={handleSelectSession}
                    onNewChat={handleNewChat}
                    onDeleteSession={handleDeleteSession}
                    onDeleteAllSessions={handleDeleteAllSessions}
                    onRefreshSessions={loadSessions}
                    chatbotType={chatbotType}
                    setChatbotType={handleChatbotTypeChange}
                    handleLogout={handleLogout}
                />

                <SidebarInset className="flex flex-col h-screen overflow-hidden">
                    <header className="flex h-14 items-center gap-2 border-b bg-background px-4 shrink-0">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <SidebarTrigger />
                            </TooltipTrigger>
                            <TooltipContent side="bottom">
                                <p>Toggle Sidebar</p>
                            </TooltipContent>
                        </Tooltip>
                        <div className="w-px h-6 bg-border mx-2" />
                        <span className="font-semibold">
                            {chatbotType === 'SOP' ? 'SOP' : chatbotType === 'INSW' ? 'HS Code' : 'General'} Assistant
                        </span>
                        <div className="ml-auto">
                            {/* Add extra header items if needed */}
                        </div>
                    </header>
                    <div className="flex-1 min-h-0 overflow-hidden">
                        {children}
                    </div>
                </SidebarInset>
            </SidebarProvider>
        </TooltipProvider>
    );
}

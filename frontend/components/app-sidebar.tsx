import * as React from "react"
import { useState } from "react"
import { MessageSquare, Plus, Trash2, MoreHorizontal, Pencil } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"

import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupContent,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuAction,
    SidebarMenuButton,
    SidebarMenuItem,
    useSidebar,
} from "@/components/ui/sidebar"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ModeToggle } from "@/components/mode-toggle"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from "@/utils/cn"
import { fetchAPI } from "@/utils/api"

import { BotSwitcher } from "./bot-switcher"
import { NavUser } from "./nav-user"

interface Session {
    session_id: string;
    title: string;
    last_activity: string;
    message_count?: number
}

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
    sessions: Session[]
    currentSessionId: string | null
    onSelectSession: (id: string) => void
    onNewChat: () => void
    onDeleteSession: (id: string) => void
    chatbotType: 'SOP' | 'INSW' | 'OTHERS'
    setChatbotType: (type: 'SOP' | 'INSW' | 'OTHERS') => void
    user: any
    handleLogout: () => void
    onRefreshSessions?: () => void
    onDeleteAllSessions: () => void
}

export function AppSidebar({
    sessions,
    currentSessionId,
    onSelectSession,
    onNewChat,
    onDeleteSession,
    chatbotType,
    setChatbotType,
    user,
    handleLogout,
    onRefreshSessions,
    onDeleteAllSessions,
    ...props
}: AppSidebarProps) {
    const { setOpenMobile } = useSidebar()

    // Dialog States
    const [deleteId, setDeleteId] = useState<string | null>(null)
    const [deleteAllOpen, setDeleteAllOpen] = useState(false)
    const [renameSessionId, setRenameSessionId] = useState<string | null>(null)
    const [newTitle, setNewTitle] = useState("")

    const getChatbotLabel = (type: string) => {
        if (type === 'SOP') return 'SOP Assistant';
        if (type === 'INSW') return 'HS Code Assistant';
        return 'General Assistant';
    }

    const handleRenameSession = async () => {
        if (!renameSessionId || !newTitle.trim()) return;

        try {
            await fetchAPI(`/chat/sessions/${renameSessionId}/title`, {
                method: 'PATCH',
                body: JSON.stringify({ title: newTitle }),
            });
            if (onRefreshSessions) {
                onRefreshSessions();
            } else {
                window.location.reload();
            }
        } catch (error) {
            console.error("Failed to rename session", error);
        } finally {
            setRenameSessionId(null);
            setNewTitle("");
        }
    }

    return (
        <>
            <Sidebar collapsible="icon" className="border-none" {...props}>
                <SidebarHeader>
                    <div className="flex items-center justify-between p-2 group-data-[collapsible=icon]:justify-center">
                        <div className="flex items-center gap-2 font-bold text-xl px-2 group-data-[collapsible=icon]:hidden truncate">
                            <span>EXIM Chat</span>
                        </div>
                        <div className="group-data-[collapsible=icon]:hidden">
                            <ModeToggle />
                        </div>
                    </div>

                    <BotSwitcher chatbotType={chatbotType} setChatbotType={setChatbotType} />
                </SidebarHeader>

                <SidebarContent>
                    <SidebarGroup>
                        <SidebarGroupContent>
                            <SidebarMenu>
                                <SidebarMenuItem>
                                    <SidebarMenuButton
                                        onClick={onNewChat}
                                        className="bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground cursor-pointer"
                                        tooltip="New Chat"
                                    >
                                        <Plus className="h-4 w-4" />
                                        <span>New Chat</span>
                                    </SidebarMenuButton>
                                </SidebarMenuItem>
                            </SidebarMenu>
                        </SidebarGroupContent>
                    </SidebarGroup>

                    <SidebarGroup className="flex-1 overflow-auto">
                        <SidebarGroupLabel>Chats</SidebarGroupLabel>
                        <SidebarGroupContent>
                            <SidebarMenu>
                                <AnimatePresence initial={false} mode="popLayout">
                                    {sessions.map((session) => (
                                        <motion.li
                                            key={session.session_id}
                                            layout
                                            initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                                            animate={{ opacity: 1, height: 'auto', marginBottom: 4 }}
                                            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                                            transition={{ duration: 0.2 }}
                                            className="group/menu-item relative"
                                        >
                                            <SidebarMenuButton
                                                isActive={currentSessionId === session.session_id}
                                                onClick={() => {
                                                    onSelectSession(session.session_id)
                                                    setOpenMobile(false)
                                                }}
                                                tooltip={session.title || 'New Chat'}
                                                className={cn(
                                                    "transition-all duration-200 cursor-pointer",
                                                    currentSessionId === session.session_id
                                                        ? "!bg-accent !text-accent-foreground font-medium"
                                                        : "text-muted-foreground"
                                                )}
                                            >
                                                <MessageSquare className="h-4 w-4" />
                                                <span className="truncate">{session.title || 'New Chat'}</span>
                                            </SidebarMenuButton>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <SidebarMenuAction showOnHover title="More" className="cursor-pointer">
                                                        <MoreHorizontal />
                                                        <span className="sr-only">More</span>
                                                    </SidebarMenuAction>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent className="w-48" side="right" align="start">
                                                    <DropdownMenuItem
                                                        onClick={() => {
                                                            setNewTitle(session.title || "");
                                                            setRenameSessionId(session.session_id);
                                                        }}
                                                        className="cursor-pointer"
                                                    >
                                                        <Pencil className="mr-2 h-4 w-4 text-muted-foreground" />
                                                        <span>Rename</span>
                                                    </DropdownMenuItem>
                                                    <DropdownMenuSeparator />
                                                    <DropdownMenuItem
                                                        onClick={() => setDeleteId(session.session_id)}
                                                        className="cursor-pointer text-destructive focus:text-destructive"
                                                    >
                                                        <Trash2 className="mr-2 h-4 w-4" />
                                                        <span>Delete</span>
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </motion.li>
                                    ))}
                                </AnimatePresence>
                            </SidebarMenu>
                        </SidebarGroupContent>
                    </SidebarGroup>

                    <SidebarGroup className="mt-auto">
                        <SidebarGroupContent>
                            <SidebarMenu>
                                <SidebarMenuItem>
                                    <SidebarMenuButton
                                        onClick={() => setDeleteAllOpen(true)}
                                        disabled={sessions.length === 0}
                                        className={cn(
                                            "text-destructive hover:text-destructive hover:bg-destructive/10 cursor-pointer",
                                            sessions.length === 0 && "opacity-50 cursor-not-allowed"
                                        )}
                                    >
                                        <Trash2 className="h-4 w-4" />
                                        <span>Clear all chats</span>
                                    </SidebarMenuButton>
                                </SidebarMenuItem>
                            </SidebarMenu>
                        </SidebarGroupContent>
                    </SidebarGroup>
                </SidebarContent>

                <SidebarFooter>
                    <NavUser user={user} handleLogout={handleLogout} />
                </SidebarFooter>
            </Sidebar >

            {/* Delete All Confirmation Dialog */}
            < Dialog open={deleteAllOpen} onOpenChange={setDeleteAllOpen} >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Clear all chats?</DialogTitle>
                        <DialogDescription>
                            This will permanently delete <strong>all</strong> chat history for {getChatbotLabel(chatbotType)}.
                            This action cannot be undone.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteAllOpen(false)}>Cancel</Button>
                        <Button
                            variant="destructive"
                            onClick={() => {
                                onDeleteAllSessions();
                                setDeleteAllOpen(false);
                            }}
                        >
                            Clear all
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog >

            {/* Delete Confirmation Dialog */}
            < Dialog open={!!deleteId
            } onOpenChange={(open) => !open && setDeleteId(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Delete Conversation?</DialogTitle>
                        <DialogDescription>
                            This action cannot be undone. This will permanently delete the chat history.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
                        <Button
                            variant="destructive"
                            onClick={() => {
                                if (deleteId) {
                                    onDeleteSession(deleteId);
                                    setDeleteId(null);
                                }
                            }}
                        >
                            Delete
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog >

            {/* Rename Dialog */}
            < Dialog open={!!renameSessionId} onOpenChange={(open) => !open && setRenameSessionId(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Rename Chat</DialogTitle>
                        <DialogDescription>
                            Enter a new title for this chat session.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="title" className="text-right">
                                Title
                            </Label>
                            <Input
                                id="title"
                                value={newTitle}
                                onChange={(e) => setNewTitle(e.target.value)}
                                className="col-span-3"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setRenameSessionId(null)}>Cancel</Button>
                        <Button onClick={handleRenameSession}>Save</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog >
        </>
    )
}

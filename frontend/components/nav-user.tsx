"use strict";
import { useRouter } from "next/navigation"
import { Shield, LogOut, MoreHorizontal, UserPen, Activity } from "lucide-react"

import {
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
    useSidebar,
} from "@/components/ui/sidebar"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

interface NavUserProps {
    user: {
        username: string;
        display_name?: string;
        role?: string;
    };
    handleLogout: () => void;
}

export function NavUser({ user, handleLogout }: NavUserProps) {
    const { isMobile } = useSidebar()
    const router = useRouter()

    // Use display_name if available, otherwise fallback to username
    const displayName = user?.display_name || user?.username;

    return (
        <SidebarMenu>
            <SidebarMenuItem>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <SidebarMenuButton
                            size="lg"
                            className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground cursor-pointer"
                        >
                            <Avatar className="h-8 w-8 rounded-lg">
                                <AvatarImage src="/icon.png" alt={displayName} />
                                <AvatarFallback className="rounded-lg">{displayName?.[0]?.toUpperCase()}</AvatarFallback>
                            </Avatar>
                            <div className="grid flex-1 text-left text-sm leading-tight ml-2">
                                <span className="truncate font-semibold">{displayName}</span>
                                <span className="truncate text-xs capitalize">{user?.role || 'User'}</span>
                            </div>
                            <MoreHorizontal className="ml-auto size-4" />
                        </SidebarMenuButton>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                        className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
                        side={isMobile ? "bottom" : "right"}
                        align="end"
                        sideOffset={4}
                    >
                        <DropdownMenuLabel className="p-0 font-normal">
                            <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                                <Avatar className="h-8 w-8 rounded-lg">
                                    <AvatarImage src="/icon.png" alt={displayName} />
                                    <AvatarFallback className="rounded-lg">{displayName?.[0]?.toUpperCase()}</AvatarFallback>
                                </Avatar>
                                <div className="grid flex-1 text-left text-sm leading-tight">
                                    <span className="truncate font-semibold">{displayName}</span>
                                    <span className="truncate text-xs text-muted-foreground capitalize">{user?.role}</span>
                                </div>
                            </div>
                        </DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={() => router.push('/profile')} className="cursor-pointer">
                            <UserPen className="mr-2 h-4 w-4" />
                            Edit Profile
                        </DropdownMenuItem>
                        {user?.role === 'admin' && (
                            <>
                                <DropdownMenuItem onClick={() => router.push('/admin')} className="cursor-pointer">
                                    <Shield className="mr-2 h-4 w-4" />
                                    Admin Panel
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => router.push('/developer')} className="cursor-pointer">
                                    <Activity className="mr-2 h-4 w-4" />
                                    Developer Dashboard
                                </DropdownMenuItem>
                            </>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive focus:text-destructive">
                            <LogOut className="mr-2 h-4 w-4" />
                            Log out
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </SidebarMenuItem>
        </SidebarMenu>
    )
}

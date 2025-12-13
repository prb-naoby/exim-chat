'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { fetchAPI, getCurrentUser } from '@/utils/api';
import { Trash2, UserPlus, ArrowLeft, Shield, Check, X, Clock, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export default function AdminPage() {
    const router = useRouter();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [users, setUsers] = useState<any[]>([]);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [pendingUsers, setPendingUsers] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    // Form State
    const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user' });
    const [createError, setCreateError] = useState('');

    // Dialog State
    const [deleteUserId, setDeleteUserId] = useState<number | null>(null);
    const [rejectUserId, setRejectUserId] = useState<number | null>(null);

    useEffect(() => {
        const user = getCurrentUser();
        if (!user || user.role !== 'admin') {
            router.push('/dashboard');
            return;
        }
        loadUsers();
        loadPendingUsers();
    }, [router]);

    const loadUsers = async () => {
        try {
            const res = await fetchAPI('/admin/users');
            if (res.ok) {
                setUsers(await res.json());
            }
        } catch (e) {
            console.error("Failed to load users", e);
        } finally {
            setLoading(false);
        }
    };

    const loadPendingUsers = async () => {
        try {
            const res = await fetchAPI('/admin/pending-users');
            if (res.ok) {
                setPendingUsers(await res.json());
            }
        } catch (e) {
            console.error("Failed to load pending users", e);
        }
    };

    const handleCreateUser = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreateError('');

        try {
            const res = await fetchAPI('/admin/users', {
                method: 'POST',
                body: JSON.stringify(newUser)
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to create user");
            }

            setNewUser({ username: '', password: '', role: 'user' });
            loadUsers();
        } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
            setCreateError(err.message);
        }
    };

    const handleDeleteUser = async (id: number) => {
        try {
            await fetchAPI(`/admin/users/${id}`, { method: 'DELETE' });
            loadUsers();
        } catch (e) {
            console.error("Failed to delete user", e);
        }
    };

    const handleApproveUser = async (id: number) => {
        try {
            const res = await fetchAPI(`/admin/pending-users/${id}/approve`, { method: 'POST' });
            if (res.ok) {
                loadPendingUsers();
                loadUsers();
            }
        } catch (e) {
            console.error("Failed to approve user", e);
        }
    };

    const handleRejectUser = async (id: number) => {
        try {
            await fetchAPI(`/admin/pending-users/${id}/reject`, { method: 'POST' });
            loadPendingUsers();
        } catch (e) {
            console.error("Failed to reject user", e);
        }
    };

    return (
        <TooltipProvider delayDuration={300}>
            <div className="min-h-screen bg-background p-4 md:p-8">
                <div className="max-w-4xl mx-auto space-y-6">
                    {/* Header */}
                    <div className="flex items-center gap-4">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => router.push('/dashboard')}
                                >
                                    <ArrowLeft className="h-5 w-5" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent><p>Back to Dashboard</p></TooltipContent>
                        </Tooltip>
                        <div className="flex items-center gap-2">
                            <Shield className="h-6 w-6 text-primary" />
                            <h1 className="text-2xl font-bold">Admin Dashboard</h1>
                        </div>
                    </div>

                    {/* Pending Users Card */}
                    {pendingUsers.length > 0 && (
                        <Card className="border-muted bg-muted/30">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Clock className="h-5 w-5 text-muted-foreground" />
                                    Pending Registrations
                                    <span className="ml-auto bg-primary text-primary-foreground text-xs px-2 py-0.5 rounded-full">
                                        {pendingUsers.length}
                                    </span>
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    {pendingUsers.map((user) => (
                                        <div
                                            key={user.id}
                                            className="flex items-center justify-between p-3 bg-background rounded-lg border"
                                        >
                                            <div className="flex flex-col">
                                                <span className="font-medium">{user.username}</span>
                                                <span className="text-sm text-muted-foreground">{user.email}</span>
                                                <span className="text-xs text-muted-foreground">
                                                    Requested: {user.requested_at ? new Date(user.requested_at).toLocaleDateString('en-US', { timeZone: 'Asia/Jakarta' }) : 'Unknown'}
                                                </span>
                                            </div>
                                            <div className="flex gap-2">
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            size="sm"
                                                            onClick={() => handleApproveUser(user.id)}
                                                        >
                                                            <Check className="h-4 w-4 mr-1" />
                                                            Approve
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent><p>Approve user registration</p></TooltipContent>
                                                </Tooltip>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => setRejectUserId(user.id)}
                                                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                                                        >
                                                            <X className="h-4 w-4 mr-1" />
                                                            Reject
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent><p>Reject user registration</p></TooltipContent>
                                                </Tooltip>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Create User Card */}
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <UserPlus className="h-5 w-5" />
                                Add New User
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleCreateUser} className="flex flex-col md:flex-row gap-4 items-end">
                                <div className="flex-1 w-full space-y-2">
                                    <Label htmlFor="username">Username</Label>
                                    <Input
                                        id="username"
                                        type="text"
                                        required
                                        value={newUser.username}
                                        onChange={e => setNewUser({ ...newUser, username: e.target.value })}
                                    />
                                </div>
                                <div className="flex-1 w-full space-y-2">
                                    <Label htmlFor="password">Password</Label>
                                    <Input
                                        id="password"
                                        type="text"
                                        required
                                        value={newUser.password}
                                        onChange={e => setNewUser({ ...newUser, password: e.target.value })}
                                    />
                                </div>
                                <div className="w-full md:w-32 space-y-2">
                                    <Label htmlFor="role">Role</Label>
                                    <Select
                                        value={newUser.role}
                                        onValueChange={(value) => setNewUser({ ...newUser, role: value })}
                                    >
                                        <SelectTrigger>
                                            <SelectValue placeholder="Select role" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="user">User</SelectItem>
                                            <SelectItem value="admin">Admin</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <Button type="submit" className="w-full md:w-auto">
                                    Add User
                                </Button>
                            </form>
                            {createError && <p className="text-destructive text-sm mt-3">{createError}</p>}
                        </CardContent>
                    </Card>

                    <Separator />

                    {/* Users List Card */}
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Users className="h-5 w-5" />
                                Registered Users
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-0">
                            <div className="overflow-x-auto">
                                <table className="min-w-full text-left text-sm">
                                    <thead className="bg-muted/50">
                                        <tr>
                                            <th className="px-6 py-3 font-medium text-muted-foreground">ID</th>
                                            <th className="px-6 py-3 font-medium text-muted-foreground">User</th>
                                            <th className="px-6 py-3 font-medium text-muted-foreground">Role</th>
                                            <th className="px-6 py-3 font-medium text-muted-foreground">Requested</th>
                                            <th className="px-6 py-3 font-medium text-muted-foreground">Approved</th>
                                            <th className="px-6 py-3 font-medium text-muted-foreground">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {loading ? (
                                            <tr><td colSpan={6} className="p-6 text-center">Loading...</td></tr>
                                        ) : users.map((u) => (
                                            <tr key={u.id} className="hover:bg-muted/50">
                                                <td className="px-6 py-4">{u.id}</td>
                                                <td className="px-6 py-4 font-medium">
                                                    <div className="flex flex-col">
                                                        <span>{u.display_name || u.username}</span>
                                                        {/* Username hidden as per request */}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${u.role === 'admin'
                                                        ? 'bg-primary/10 text-primary'
                                                        : 'bg-muted text-muted-foreground'
                                                        }`}>
                                                        {u.role}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4 text-muted-foreground">
                                                    {u.requested_at ? new Date(u.requested_at).toLocaleDateString('en-US', { timeZone: 'Asia/Jakarta' }) : '—'}
                                                </td>
                                                <td className="px-6 py-4 text-muted-foreground">
                                                    {u.created_at ? new Date(u.created_at).toLocaleDateString('en-US', { timeZone: 'Asia/Jakarta' }) : '—'}
                                                </td>
                                                <td className="px-6 py-4">
                                                    {u.username !== 'admin' && (
                                                        <Tooltip>
                                                            <TooltipTrigger asChild>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    onClick={() => setDeleteUserId(u.id)}
                                                                    className="h-8 w-8 text-destructive hover:text-destructive"
                                                                >
                                                                    <Trash2 className="h-4 w-4" />
                                                                </Button>
                                                            </TooltipTrigger>
                                                            <TooltipContent><p>Delete user</p></TooltipContent>
                                                        </Tooltip>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                        {!loading && users.length === 0 && (
                                            <tr><td colSpan={6} className="p-6 text-center text-muted-foreground">No users found</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Dialogs */}
                    <Dialog open={!!deleteUserId} onOpenChange={(open) => !open && setDeleteUserId(null)}>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Delete User?</DialogTitle>
                                <DialogDescription>
                                    Are you sure you want to delete this user? This action cannot be undone.
                                </DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                                <Button variant="outline" onClick={() => setDeleteUserId(null)}>Cancel</Button>
                                <Button
                                    variant="destructive"
                                    onClick={() => {
                                        if (deleteUserId) {
                                            handleDeleteUser(deleteUserId);
                                            setDeleteUserId(null);
                                        }
                                    }}
                                >
                                    Delete
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>

                    <Dialog open={!!rejectUserId} onOpenChange={(open) => !open && setRejectUserId(null)}>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Reject User Registration?</DialogTitle>
                                <DialogDescription>
                                    Are you sure you want to reject this user registration?
                                </DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                                <Button variant="outline" onClick={() => setRejectUserId(null)}>Cancel</Button>
                                <Button
                                    variant="destructive"
                                    onClick={() => {
                                        if (rejectUserId) {
                                            handleRejectUser(rejectUserId);
                                            setRejectUserId(null);
                                        }
                                    }}
                                >
                                    Reject
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>
            </div>
        </TooltipProvider>
    );
}

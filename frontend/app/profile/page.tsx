'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { fetchAPI, getCurrentUser } from '@/utils/api';
import { ArrowLeft, User, KeyRound, Loader2, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export default function ProfilePage() {
    const router = useRouter();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [user, setUser] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    // Profile Form State
    const [displayName, setDisplayName] = useState('');
    const [profileLoading, setProfileLoading] = useState(false);
    const [profileSuccess, setProfileSuccess] = useState(false);
    const [profileError, setProfileError] = useState('');

    // Password Form State
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [passwordLoading, setPasswordLoading] = useState(false);
    const [passwordSuccess, setPasswordSuccess] = useState(false);
    const [passwordError, setPasswordError] = useState('');

    useEffect(() => {
        const currentUser = getCurrentUser();
        if (!currentUser) {
            router.push('/login');
            return;
        }
        setUser(currentUser);
        setDisplayName(currentUser.display_name || currentUser.username);
        setLoading(false);
    }, [router]);

    const handleProfileUpdate = async (e: React.FormEvent) => {
        e.preventDefault();
        setProfileError('');
        setProfileSuccess(false);
        setProfileLoading(true);

        try {
            const res = await fetchAPI('/auth/profile', {
                method: 'PATCH',
                body: JSON.stringify({ display_name: displayName })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to update profile');
            }

            // Update local storage
            const updatedUser = { ...user, display_name: displayName };
            localStorage.setItem('user', JSON.stringify(updatedUser));
            setUser(updatedUser);
            setProfileSuccess(true);

            // Clear success after 3 seconds
            setTimeout(() => setProfileSuccess(false), 3000);
        } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
            setProfileError(err.message);
        } finally {
            setProfileLoading(false);
        }
    };

    const handlePasswordChange = async (e: React.FormEvent) => {
        e.preventDefault();
        setPasswordError('');
        setPasswordSuccess(false);

        // Validation
        if (newPassword !== confirmPassword) {
            setPasswordError('New passwords do not match');
            return;
        }
        if (newPassword.length < 6) {
            setPasswordError('Password must be at least 6 characters');
            return;
        }

        setPasswordLoading(true);

        try {
            const res = await fetchAPI('/auth/password', {
                method: 'PATCH',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to change password');
            }

            // Clear form and show success
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
            setPasswordSuccess(true);

            // Clear success after 3 seconds
            setTimeout(() => setPasswordSuccess(false), 3000);
        } catch (err: any) { // eslint-disable-line @typescript-eslint/no-explicit-any
            setPasswordError(err.message);
        } finally {
            setPasswordLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <Loader2 className="h-8 w-8 animate-spin" />
            </div>
        );
    }

    return (
        <TooltipProvider delayDuration={300}>
            <div className="min-h-screen bg-background p-4 md:p-8">
                <div className="max-w-2xl mx-auto space-y-6">
                    {/* Header */}
                    <div className="flex items-center gap-4">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => router.back()}
                                >
                                    <ArrowLeft className="h-5 w-5" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent><p>Go back</p></TooltipContent>
                        </Tooltip>
                        <div className="flex items-center gap-3">
                            <Avatar className="h-10 w-10">
                                <AvatarImage src="/icon.png" alt={user?.display_name || user?.username} />
                                <AvatarFallback>{(user?.display_name || user?.username)?.[0]?.toUpperCase()}</AvatarFallback>
                            </Avatar>
                            <div>
                                <h1 className="text-2xl font-bold">Edit Profile</h1>
                                <p className="text-sm text-muted-foreground capitalize">{user?.role}</p>
                            </div>
                        </div>
                    </div>

                    {/* Display Name Card */}
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <User className="h-5 w-5" />
                                Display Name
                            </CardTitle>
                            <CardDescription>
                                This is the name displayed in the sidebar and throughout the app.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleProfileUpdate} className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="displayName">Display Name</Label>
                                    <Input
                                        id="displayName"
                                        type="text"
                                        value={displayName}
                                        onChange={(e) => setDisplayName(e.target.value)}
                                        placeholder="Enter your display name"
                                        required
                                    />
                                </div>
                                {profileError && (
                                    <p className="text-sm text-destructive">{profileError}</p>
                                )}
                                {profileSuccess && (
                                    <p className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1">
                                        <Check className="h-4 w-4" /> Profile updated successfully
                                    </p>
                                )}
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button type="submit" disabled={profileLoading}>
                                            {profileLoading ? (
                                                <>
                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                    Saving...
                                                </>
                                            ) : (
                                                'Save Changes'
                                            )}
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent><p>Update display name</p></TooltipContent>
                                </Tooltip>
                            </form>
                        </CardContent>
                    </Card>

                    <Separator />

                    {/* Password Change Card */}
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <KeyRound className="h-5 w-5" />
                                Change Password
                            </CardTitle>
                            <CardDescription>
                                Update your password to keep your account secure.
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handlePasswordChange} className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="currentPassword">Current Password</Label>
                                    <Input
                                        id="currentPassword"
                                        type="password"
                                        value={currentPassword}
                                        onChange={(e) => setCurrentPassword(e.target.value)}
                                        placeholder="Enter current password"
                                        required
                                        autoComplete="current-password"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="newPassword">New Password</Label>
                                    <Input
                                        id="newPassword"
                                        type="password"
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        placeholder="Enter new password"
                                        required
                                        autoComplete="new-password"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="confirmPassword">Confirm New Password</Label>
                                    <Input
                                        id="confirmPassword"
                                        type="password"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        placeholder="Confirm new password"
                                        required
                                        autoComplete="new-password"
                                    />
                                </div>
                                {passwordError && (
                                    <p className="text-sm text-destructive">{passwordError}</p>
                                )}
                                {passwordSuccess && (
                                    <p className="text-sm text-green-600 dark:text-green-400 flex items-center gap-1">
                                        <Check className="h-4 w-4" /> Password changed successfully
                                    </p>
                                )}
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button type="submit" disabled={passwordLoading}>
                                            {passwordLoading ? (
                                                <>
                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                    Changing...
                                                </>
                                            ) : (
                                                'Change Password'
                                            )}
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent><p>Update your password</p></TooltipContent>
                                </Tooltip>
                            </form>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </TooltipProvider>
    );
}

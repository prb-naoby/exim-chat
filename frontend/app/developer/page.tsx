'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { fetchAPI, getCurrentUser } from '@/utils/api';
import {
    ArrowLeft, Activity, CheckCircle, XCircle, AlertTriangle,
    Loader2, RefreshCw, Zap, Clock, Database
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';

interface LLMLog {
    id: number;
    session_id: string;
    username: string;
    chatbot_type: string;
    status: string;
    input_tokens: number;
    output_tokens: number;
    latency_ms: number;
    error_message: string | null;
    query: string | null;
    created_at: string;
}

interface LLMStats {
    total: number;
    answered: number;
    unanswered: number;
    errors: number;
    total_input_tokens: number;
    total_output_tokens: number;
    avg_latency_ms: number;
    daily_stats: { date: string; calls: number; tokens: number }[];
}

export default function DeveloperDashboard() {
    const router = useRouter();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [user, setUser] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const [stats, setStats] = useState<LLMStats | null>(null);
    const [logs, setLogs] = useState<LLMLog[]>([]);
    const [statusFilter, setStatusFilter] = useState<string>('all');
    const [typeFilter, setTypeFilter] = useState<string>('all');

    useEffect(() => {
        const currentUser = getCurrentUser();
        if (!currentUser) {
            router.push('/login');
            return;
        }
        if (currentUser.role !== 'admin') {
            router.push('/dashboard');
            return;
        }
        setUser(currentUser);
        loadData();
    }, [router]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [statsRes, logsRes] = await Promise.all([
                fetchAPI('/dev/stats'),
                fetchAPI('/dev/logs?limit=100')
            ]);

            if (statsRes.ok) {
                const statsData = await statsRes.json();
                setStats(statsData);
            }
            if (logsRes.ok) {
                const logsData = await logsRes.json();
                setLogs(logsData.logs || []);
            }
        } catch (err) {
            console.error('Error loading developer data:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleRefresh = async () => {
        setRefreshing(true);
        await loadData();
        setRefreshing(false);
    };

    // Filter logs based on selections
    const filteredLogs = logs.filter(log => {
        if (statusFilter !== 'all' && log.status !== statusFilter) return false;
        if (typeFilter !== 'all' && log.chatbot_type !== typeFilter) return false;
        return true;
    });

    // Calculate max for chart scaling
    const maxCalls = Math.max(...(stats?.daily_stats?.map(d => d.calls) || [1]), 1);

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
                <div className="max-w-7xl mx-auto space-y-6">
                    {/* Header */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button variant="ghost" size="icon" onClick={() => router.back()}>
                                        <ArrowLeft className="h-5 w-5" />
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent><p>Go back</p></TooltipContent>
                            </Tooltip>
                            <div>
                                <h1 className="text-2xl font-bold flex items-center gap-2">
                                    <Activity className="h-6 w-6 text-primary" />
                                    Developer Dashboard
                                </h1>
                                <p className="text-sm text-muted-foreground">LLM usage analytics and logs</p>
                            </div>
                        </div>
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
                                    <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                                    Refresh
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent><p>Reload statistics</p></TooltipContent>
                        </Tooltip>
                    </div>

                    {/* Stats Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Total Calls</CardDescription>
                                <CardTitle className="text-3xl">{stats?.total || 0}</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-center text-muted-foreground text-sm">
                                    <Database className="h-4 w-4 mr-1" />
                                    All LLM requests
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Answered</CardDescription>
                                <CardTitle className="text-3xl text-green-600 dark:text-green-400">
                                    {stats?.answered || 0}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-center text-muted-foreground text-sm">
                                    <CheckCircle className="h-4 w-4 mr-1 text-green-600" />
                                    {stats?.total ? ((stats.answered / stats.total) * 100).toFixed(1) : 0}% success
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Unanswered</CardDescription>
                                <CardTitle className="text-3xl text-yellow-600 dark:text-yellow-400">
                                    {stats?.unanswered || 0}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-center text-muted-foreground text-sm">
                                    <AlertTriangle className="h-4 w-4 mr-1 text-yellow-600" />
                                    No relevant context
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Errors</CardDescription>
                                <CardTitle className="text-3xl text-red-600 dark:text-red-400">
                                    {stats?.errors || 0}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-center text-muted-foreground text-sm">
                                    <XCircle className="h-4 w-4 mr-1 text-red-600" />
                                    Failed requests
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Token Usage and Latency */}
                    <div className="grid md:grid-cols-2 gap-4">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Zap className="h-5 w-5" />
                                    Token Usage
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Input Tokens</span>
                                        <span className="font-mono">{(stats?.total_input_tokens || 0).toLocaleString()}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Output Tokens</span>
                                        <span className="font-mono">{(stats?.total_output_tokens || 0).toLocaleString()}</span>
                                    </div>
                                    <div className="border-t pt-3 flex justify-between font-semibold">
                                        <span>Total Tokens</span>
                                        <span className="font-mono">
                                            {((stats?.total_input_tokens || 0) + (stats?.total_output_tokens || 0)).toLocaleString()}
                                        </span>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Clock className="h-5 w-5" />
                                    Performance
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-3">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Avg Latency</span>
                                        <span className="font-mono">{stats?.avg_latency_ms || 0}ms</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Avg Tokens/Call</span>
                                        <span className="font-mono">
                                            {stats?.total ? Math.round(((stats.total_input_tokens || 0) + (stats.total_output_tokens || 0)) / stats.total) : 0}
                                        </span>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Daily Chart (CSS-based) */}
                    {stats?.daily_stats && stats.daily_stats.length > 0 && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Daily API Calls (Last 7 Days)</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex items-end gap-2 h-32">
                                    {stats.daily_stats.map((day, idx) => (
                                        <Tooltip key={idx}>
                                            <TooltipTrigger asChild>
                                                <div className="flex-1 flex flex-col items-center gap-1">
                                                    <div
                                                        className="w-full bg-primary rounded-t transition-all hover:bg-primary/80"
                                                        style={{ height: `${(day.calls / maxCalls) * 100}%`, minHeight: '4px' }}
                                                    />
                                                    <span className="text-xs text-muted-foreground">
                                                        {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short', timeZone: 'Asia/Jakarta' })}
                                                    </span>
                                                </div>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <p>{day.date}: {day.calls} calls, {day.tokens?.toLocaleString() || 0} tokens</p>
                                            </TooltipContent>
                                        </Tooltip>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Logs Table */}
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-lg">Recent Logs</CardTitle>
                                <div className="flex gap-2">
                                    <Select value={statusFilter} onValueChange={setStatusFilter}>
                                        <SelectTrigger className="w-32">
                                            <SelectValue placeholder="Status" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Status</SelectItem>
                                            <SelectItem value="answered">Answered</SelectItem>
                                            <SelectItem value="unanswered">Unanswered</SelectItem>
                                            <SelectItem value="error">Error</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Select value={typeFilter} onValueChange={setTypeFilter}>
                                        <SelectTrigger className="w-32">
                                            <SelectValue placeholder="Type" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Types</SelectItem>
                                            <SelectItem value="SOP">SOP</SelectItem>
                                            <SelectItem value="INSW">HS Code</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="p-0">
                            <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                                <table className="min-w-full text-left text-sm">
                                    <thead className="bg-muted/50 sticky top-0">
                                        <tr>
                                            <th className="px-4 py-3 font-medium text-muted-foreground">Time</th>
                                            <th className="px-4 py-3 font-medium text-muted-foreground">User</th>
                                            <th className="px-4 py-3 font-medium text-muted-foreground">Type</th>
                                            <th className="px-4 py-3 font-medium text-muted-foreground">Status</th>
                                            <th className="px-4 py-3 font-medium text-muted-foreground">Tokens</th>
                                            <th className="px-4 py-3 font-medium text-muted-foreground">Latency</th>
                                            <th className="px-4 py-3 font-medium text-muted-foreground">Query</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {filteredLogs.length === 0 ? (
                                            <tr>
                                                <td colSpan={7} className="p-6 text-center text-muted-foreground">
                                                    No logs found
                                                </td>
                                            </tr>
                                        ) : filteredLogs.map((log) => (
                                            <tr key={log.id} className="hover:bg-muted/50">
                                                <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                                                    {new Date(log.created_at).toLocaleString('en-US', { timeZone: 'Asia/Jakarta' })}
                                                </td>
                                                <td className="px-4 py-3 font-medium">{log.username}</td>
                                                <td className="px-4 py-3">
                                                    <Badge variant="outline">{log.chatbot_type}</Badge>
                                                </td>
                                                <td className="px-4 py-3">
                                                    <Badge
                                                        variant={
                                                            log.status === 'answered' ? 'default' :
                                                                log.status === 'error' ? 'destructive' : 'secondary'
                                                        }
                                                    >
                                                        {log.status}
                                                    </Badge>
                                                </td>
                                                <td className="px-4 py-3 font-mono text-xs">
                                                    {log.input_tokens + log.output_tokens}
                                                </td>
                                                <td className="px-4 py-3 font-mono text-xs">
                                                    {log.latency_ms}ms
                                                </td>
                                                <td className="px-4 py-3 max-w-[200px] truncate" title={log.query || ''}>
                                                    {log.query || '—'}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </TooltipProvider>
    );
}

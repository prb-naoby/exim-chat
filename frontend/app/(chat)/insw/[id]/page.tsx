'use client';

import { useState, useEffect, use } from 'react';
import { ChatInterface } from '@/components/ChatInterface';
import { fetchAPI } from '@/utils/api';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    timestamp?: string;
}

export default function INSWChatPage({ params }: { params: Promise<{ id: string }> }) {
    const resolvedParams = use(params);
    const sessionId = resolvedParams.id;
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (sessionId) {
            loadHistory();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId]);

    const loadHistory = async () => {
        setLoading(true);
        try {
            const res = await fetchAPI(`/chat/history/${sessionId}`);
            if (res.ok) {
                const data = await res.json();
                setMessages(data);
            }
        } catch (e) {
            console.error("Error loading history", e);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground"></div>
            </div>
        );
    }

    return (
        <ChatInterface
            chatbotType="INSW"
            sessionId={sessionId}
            initialMessages={messages}
            onMessageSent={() => { }}
        />
    );
}

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated } from '@/utils/api';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated()) {
      router.push('/sop');
    } else {
      router.push('/login');
    }
  }, [router]);

  return (
    <div className="flex h-screen items-center justify-center" suppressHydrationWarning>
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-foreground" suppressHydrationWarning></div>
    </div>
  );
}

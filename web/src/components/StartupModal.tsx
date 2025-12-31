'use client';

import { useState, useEffect, useRef } from 'react';
import { HoneycombButton } from './HoneycombButton';
import { claudeApi } from '@/lib/api';

interface StartupModalProps {
  onClose: () => void;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export function StartupModal({ onClose }: StartupModalProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initial greeting from Claude on mount
  useEffect(() => {
    const fetchGreeting = async () => {
      try {
        const result = await claudeApi.chat(
          'Greet the user warmly and introduce yourself as the HIVE215 AI assistant. Ask how you can help them today with voice assistants, subscriptions, or any questions about the platform. Keep it brief (2-3 sentences).',
          'You are the HIVE215 AI assistant greeting a new visitor to the premier voice assistant platform. Be warm, professional, and concise.'
        );
        setMessages([{ role: 'assistant', content: result.response }]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect to Claude');
        setMessages([{
          role: 'assistant',
          content: 'Welcome to HIVE215! I\'m your AI assistant. How can I help you today with our voice assistant platform?'
        }]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchGreeting();
  }, []);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);
    setError(null);

    try {
      const result = await claudeApi.chat(userMessage);
      setMessages(prev => [...prev, { role: 'assistant', content: result.response }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-zinc-900 border border-gold/30 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-gold/20 to-transparent border-b border-gold/20 px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gold/20 flex items-center justify-center">
              <span className="text-gold text-xl">AI</span>
            </div>
            <div>
              <h2 className="text-lg font-bold text-gold">HIVE215 Assistant</h2>
              <p className="text-xs text-gray-400">Powered by Claude</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Messages */}
        <div className="h-80 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] px-4 py-2 rounded-2xl ${
                  msg.role === 'user'
                    ? 'bg-gold text-black rounded-br-sm'
                    : 'bg-zinc-800 text-white rounded-bl-sm'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}
          {isLoading && messages.length > 0 && (
            <div className="flex justify-start">
              <div className="bg-zinc-800 text-white px-4 py-2 rounded-2xl rounded-bl-sm">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gold rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-gold rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-gold rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          {isLoading && messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="flex justify-center gap-1 mb-2">
                  <span className="w-3 h-3 bg-gold rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-3 h-3 bg-gold rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-3 h-3 bg-gold rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <p className="text-gray-400 text-sm">Connecting to Claude...</p>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Error */}
        {error && (
          <div className="px-4 pb-2">
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 text-red-400 text-xs">
              {error}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-gold/20 p-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask me anything..."
              disabled={isLoading}
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-gold/50 disabled:opacity-50"
            />
            <HoneycombButton
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              size="sm"
            >
              Send
            </HoneycombButton>
          </div>
          <p className="text-xs text-gray-500 mt-2 text-center">
            Press Enter to send or click the button
          </p>
        </div>

        {/* Quick Actions */}
        <div className="border-t border-gold/10 px-4 py-3 bg-zinc-900/50">
          <div className="flex gap-2 overflow-x-auto pb-1">
            <button
              onClick={() => setInput('What can I do with HIVE215?')}
              className="px-3 py-1 text-xs bg-zinc-800 text-gray-300 rounded-full whitespace-nowrap hover:bg-zinc-700 transition-colors"
            >
              What can I do?
            </button>
            <button
              onClick={() => setInput('Tell me about pricing plans')}
              className="px-3 py-1 text-xs bg-zinc-800 text-gray-300 rounded-full whitespace-nowrap hover:bg-zinc-700 transition-colors"
            >
              Pricing plans
            </button>
            <button
              onClick={() => setInput('How do voice assistants work?')}
              className="px-3 py-1 text-xs bg-zinc-800 text-gray-300 rounded-full whitespace-nowrap hover:bg-zinc-700 transition-colors"
            >
              How it works
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

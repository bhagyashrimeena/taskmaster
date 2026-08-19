declare module "@/lib/chat-storage.js" {
  type StoredMessage = {
    role: string;
    text: string;
    response?: import("./types").ConversationResponse;
    status?: "working" | "error";
  };

  type StoredThread = {
    conversation_id?: string;
    target?: { type: string; id?: string; title: string };
    title?: string;
    messages: StoredMessage[];
    latest_response?: import("./types").ConversationResponse;
    unread_count?: number;
    updated_at?: string;
  };

  export function readStoredThread(key?: string): StoredThread | null;
  export function writeStoredThread(thread: StoredThread, key?: string): void;
  export function writeStoredThread(key: string, thread: StoredThread): void;
  export function clearStoredThread(key?: string): void;
}
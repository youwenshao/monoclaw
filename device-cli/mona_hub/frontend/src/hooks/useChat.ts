import { useCallback, useRef, useState, useEffect } from "react";
import { 
  sendChatMessage, 
  abortChatMessage, 
  getConversation, 
  type ChatMessage 
} from "@/lib/api";

export function useChat(initialConversationId?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>(initialConversationId);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (initialConversationId && initialConversationId !== "new") {
      setConversationId(initialConversationId);
      setIsLoading(true);
      getConversation(initialConversationId)
        .then((conv) => {
          setMessages(conv.messages);
        })
        .catch(() => {
          setMessages([]);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setConversationId(undefined);
      setMessages([]);
    }
  }, [initialConversationId]);

  const sendMessage = useCallback(
    async (text: string) => {
      const userMessage: ChatMessage = { role: "user", content: text };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      try {
        const response = await sendChatMessage(text, conversationId);
        setConversationId(response.conversation_id);
        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: response.response,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Sorry, I encountered an error. Please try again." },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId],
  );

  const sendMessageStream = useCallback(
    async (text: string, modelId?: string, toolId?: string) => {
      const userMessage: ChatMessage = { role: "user", content: text };
      setMessages((prev) => [...prev, userMessage]);
      setIsStreaming(true);

      abortRef.current = new AbortController();

      try {
        const response = await fetch("/api/chat/message/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            conversation_id: conversationId,
            model_id: modelId,
            tool_id: toolId,
          }),
          signal: abortRef.current.signal,
        });

        if (!response.ok || !response.body) {
          throw new Error("Stream failed");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantContent = "";

        setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6));
              if (data.error) {
                setMessages((prev) => {
                  const updated = [...prev];
                  if (updated.length > 0 && updated[updated.length - 1].role === "assistant") {
                    updated[updated.length - 1] = {
                      role: "assistant",
                      content: data.error,
                    };
                  }
                  return updated;
                });
                break;
              }
              if (data.token) {
                assistantContent += data.token;
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    role: "assistant",
                    content: assistantContent,
                  };
                  return updated;
                });
              }
              if (data.done && data.conversation_id) {
                setConversationId(data.conversation_id);
              }
            } catch {
              // skip malformed SSE lines
            }
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // User aborted — keep partial content
        } else {
          setMessages((prev) => {
            const updated = [...prev];
            if (
              updated.length > 0 &&
              updated[updated.length - 1].role === "assistant" &&
              !updated[updated.length - 1].content
            ) {
              updated[updated.length - 1] = {
                role: "assistant",
                content: "Sorry, I encountered an error. Please try again.",
              };
            }
            return updated;
          });
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [conversationId],
  );

  const abortGeneration = useCallback(() => {
    abortRef.current?.abort();
    abortChatMessage().catch(() => {});
    setIsStreaming(false);
  }, []);

  return {
    messages,
    sendMessage,
    sendMessageStream,
    abortGeneration,
    isLoading,
    isStreaming,
    conversationId,
  };
}

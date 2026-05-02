export function initTruePresence(wsUrl, options = {}) {
    const id = options.sessionId || globalThis.crypto?.randomUUID?.() || `tp_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    const endpoint = String(wsUrl || "").replace(/\/$/, "");
    const ws = new WebSocket(`${endpoint}/ws/${id}`);
    const queue = [];

    function flushQueue() {
        while (queue.length > 0 && ws.readyState === WebSocket.OPEN) {
            ws.send(queue.shift());
        }
    }

    ws.onopen = () => {
        flushQueue();
        options.onOpen?.({ sessionId: id });
    };

    ws.onmessage = (message) => {
        const data = JSON.parse(message.data);
        options.onMessage?.(data);
        if (data.type === "trust_update") {
            options.onUpdate?.(data.data);
        }
        if (data.type === "challenge") {
            options.onChallenge?.(data.challenge);
        }
    };

    ws.onerror = (event) => options.onError?.(event);
    ws.onclose = (event) => options.onClose?.(event);

    function send(event) {
        const payload = JSON.stringify({
            session_id: id,
            timestamp: Date.now(),
            ...event,
        });
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(payload);
            return;
        }
        queue.push(payload);
    }

    return {
        sessionId: id,
        ws,
        send,
        close: () => ws.close(),
    };
}

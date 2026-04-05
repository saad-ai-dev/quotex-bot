/**
 * WebSocket Interceptor - runs in PAGE context (MAIN world).
 * Captures all WS messages and relays to content script via postMessage.
 */
(function () {
  if ((window as any).__QAM__) return;
  (window as any).__QAM__ = true;

  const OrigWS = window.WebSocket;

  (window as any).WebSocket = function (url: string, protocols?: string | string[]) {
    console.log("[QAM] WS open:", url);
    const ws = protocols ? new OrigWS(url, protocols) : new OrigWS(url);

    ws.addEventListener("message", (event: MessageEvent) => {
      try {
        const d = event.data;
        if (typeof d === "string" && d.length > 3) {
          window.postMessage({ s: "QAM", t: "str", d: d }, "*");
        } else if (d instanceof ArrayBuffer && d.byteLength > 0) {
          try {
            const txt = new TextDecoder().decode(d);
            window.postMessage({ s: "QAM", t: "bin", d: txt }, "*");
          } catch {}
        } else if (d instanceof Blob) {
          d.text().then((txt) => {
            window.postMessage({ s: "QAM", t: "blob", d: txt }, "*");
          }).catch(() => {});
        }
      } catch {}
    });

    return ws;
  } as any;

  (window as any).WebSocket.prototype = OrigWS.prototype;
  (window as any).WebSocket.CONNECTING = OrigWS.CONNECTING;
  (window as any).WebSocket.OPEN = OrigWS.OPEN;
  (window as any).WebSocket.CLOSING = OrigWS.CLOSING;
  (window as any).WebSocket.CLOSED = OrigWS.CLOSED;

  console.log("[QAM] WS hook installed");
})();

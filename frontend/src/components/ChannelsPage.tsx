import { useCallback, useEffect, useState } from "react";

const API_BASE = "";

type TikTokIntegration = { id: string; name: string };

type TikTokIntegrationsResponse = {
  connect_url: string;
  manage_url?: string;
  count: number;
  integrations: TikTokIntegration[];
  error?: string;
};

export function ChannelsPage() {
  const [tiktokConnectUrl, setTiktokConnectUrl] = useState("");
  const [tiktokManageUrl, setTiktokManageUrl] = useState("");
  const [tiktokIntegrations, setTiktokIntegrations] = useState<TikTokIntegration[]>([]);
  const [tiktokLoading, setTiktokLoading] = useState(true);

  const fetchTiktokIntegrations = useCallback(async () => {
    setTiktokLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/publishing/tiktok/integrations`);
      const data: TikTokIntegrationsResponse = await res.json().catch(() => ({}));
      setTiktokConnectUrl(data.connect_url || "");
      setTiktokManageUrl(data.manage_url || data.connect_url || "");
      setTiktokIntegrations(data.integrations || []);
    } finally {
      setTiktokLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTiktokIntegrations();
  }, [fetchTiktokIntegrations]);

  // Refrescar al volver a la pestaña (p. ej. tras gestionar la cuenta en Postiz)
  useEffect(() => {
    const onFocus = () => fetchTiktokIntegrations();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [fetchTiktokIntegrations]);

  const tiktokConnected = tiktokIntegrations.length > 0;
  const tiktokAccountLabel =
    tiktokIntegrations.length === 1 && tiktokIntegrations[0].name
      ? tiktokIntegrations[0].name
      : tiktokIntegrations.length > 1
        ? `${tiktokIntegrations.length} cuentas conectadas`
        : null;

  const openTiktokConnect = () => {
    const url = tiktokConnected ? tiktokManageUrl : tiktokConnectUrl;
    if (url) {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="channels-page">
      <h2 className="page-title">Canales conectados</h2>
      <p className="page-subtitle">Conecta tus plataformas para publicar clips directamente.</p>

      <div className="channels-grid">
        <article className="channel-card">
          <div className="channel-card-header">
            <svg className="channel-logo" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19.59 6.69a4.83 4.83 0 0 1-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 0 1-2.88 2.5 2.89 2.89 0 0 1 0-5.78c.27 0 .54.04.79.1v-3.5a6.37 6.37 0 0 0-.79-.05A6.34 6.34 0 0 0 3.15 15.3a6.34 6.34 0 0 0 6.34 6.34 6.34 6.34 0 0 0 6.34-6.34V9.05a8.27 8.27 0 0 0 4.76 1.5V7.12a4.83 4.83 0 0 1-1-.43z" />
            </svg>
            <div>
              <h3>TikTok</h3>
              <span
                className={
                  tiktokLoading
                    ? "channel-status"
                    : tiktokConnected
                      ? "channel-status channel-status--connected"
                      : "channel-status channel-status--disconnected"
                }
              >
                {tiktokLoading ? "Comprobando…" : tiktokConnected ? "Conectado" : "No conectado"}
              </span>
              {tiktokAccountLabel && (
                <span className="channel-account-name">{tiktokAccountLabel}</span>
              )}
            </div>
          </div>
          <div className="channel-card-actions">
            {tiktokConnected && (
              <button
                type="button"
                className="btn btn-ghost channel-connect-btn"
                onClick={fetchTiktokIntegrations}
                disabled={tiktokLoading}
              >
                Actualizar
              </button>
            )}
            <button
              className="btn btn-ghost channel-connect-btn"
              type="button"
              onClick={openTiktokConnect}
              disabled={!tiktokConnectUrl && !tiktokManageUrl}
            >
              {tiktokConnected ? "Gestionar en Postiz" : "Conectar"}
            </button>
          </div>
          {tiktokConnected && (
            <>
              <p className="channel-card-hint">
                Para desconectar o actualizar el nombre de la cuenta: abre <strong>Gestionar en Postiz</strong>, en Postiz desconecta TikTok y vuelve a conectarla (así se actualiza el nombre). Al volver a esta pestaña se refresca solo, o haz clic en <strong>Actualizar</strong>.
              </p>
              <p className="channel-card-hint">
                Si un video figura como publicado en Postiz pero aun no aparece en TikTok, puede haber una demora de unos minutos; revisa también la pestaña Borradores en la app de TikTok.
              </p>
            </>
          )}
        </article>

        <article className="channel-card">
          <div className="channel-card-header">
            <svg
              className="channel-logo"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
              <circle cx="12" cy="12" r="5" />
              <circle cx="17.5" cy="6.5" r="1.5" fill="currentColor" stroke="none" />
            </svg>
            <div>
              <h3>Instagram</h3>
              <span className="channel-status channel-status--disconnected">No conectado</span>
            </div>
          </div>
          <button className="btn btn-ghost channel-connect-btn" type="button">
            Conectar
          </button>
        </article>
      </div>
    </div>
  );
}

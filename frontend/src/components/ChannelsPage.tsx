export function ChannelsPage() {
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
              <span className="channel-status channel-status--disconnected">No conectado</span>
            </div>
          </div>
          <button className="btn btn-ghost channel-connect-btn" type="button">
            Conectar
          </button>
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

export function SetupInstructions() {
  return (
    <section className="setup-instructions" role="note" aria-label="Instrucciones de uso">
      <div className="setup-instructions-icon" aria-hidden="true">
        i
      </div>
      <div>
        <p className="setup-instructions-title">Flujo recomendado</p>
        <p className="setup-instructions-text">
          Configura link, formato y subtitulos. Usa el preview para validar estilo/posicion y luego
          genera clips. En la siguiente instancia podras revisar, aprobar y publicar.
        </p>
      </div>
    </section>
  );
}

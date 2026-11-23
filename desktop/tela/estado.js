// Tela local do app desktop. ?estado=iniciando|reiniciando|erro e ?mensagem=… vêm do processo
// principal (main.ts › mostrarEstado). Só usa a ponte window.cleanchain (preload).
(function () {
  const params = new URLSearchParams(location.search);
  const estado = params.get('estado') || 'iniciando';
  const textos = {
    iniciando: 'iniciando o agente…',
    reiniciando: 'reiniciando o agente…',
  };

  if (estado === 'erro') {
    document.body.className = 'is-erro';
    document.getElementById('erro-detalhe').textContent = params.get('mensagem') || '';
  } else {
    document.getElementById('texto-abertura').textContent = textos[estado] || textos.iniciando;
  }

  const ponte = window.cleanchain;
  const reiniciar = document.getElementById('reiniciar');
  const logs = document.getElementById('logs');
  if (!ponte) {
    reiniciar.disabled = true;
    logs.disabled = true;
    return;
  }
  reiniciar.addEventListener('click', () => {
    reiniciar.disabled = true;
    reiniciar.textContent = 'Reiniciando…';
    ponte.app.reiniciarServico().catch(() => {
      reiniciar.disabled = false;
      reiniciar.textContent = 'Reiniciar';
    });
  });
  logs.addEventListener('click', () => ponte.app.abrirLogs());
  if (estado === 'erro') reiniciar.focus();
})();

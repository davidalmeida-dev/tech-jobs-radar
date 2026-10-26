/**
 * Squad War Room • Client Application
 * Zero Audio Tokens • edge-tts Integration • Web Speech API • Obsidian Live Sync
 */

document.addEventListener("DOMContentLoaded", () => {
  // Estado da aplicação
  const state = {
    activeRite: "planning",
    targetAgent: "auto",
    agents: {},
    tasks: [],
    isRecording: false,
    currentAudioUrl: null,
    recognition: null,
    spacePressed: false,
  };

  // Elementos do DOM
  const audioPlayer = document.getElementById("agent-audio-player");
  const messagesContainer = document.getElementById("messages-container");
  const boardTasksContainer = document.getElementById("board-tasks-container");
  const activeRiteName = document.getElementById("active-rite-name");
  const speakerSelect = document.getElementById("speaker-select");
  const chatInput = document.getElementById("chat-input");
  const btnSend = document.getElementById("btn-send");
  const btnMic = document.getElementById("btn-mic");
  const micLabel = document.getElementById("mic-label");
  const btnBargein = document.getElementById("btn-bargein");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const btnRefreshBoard = document.getElementById("btn-refresh-board");
  const btnViewLogs = document.getElementById("btn-view-logs");
  const logsModal = document.getElementById("logs-modal");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const modalLogsContent = document.getElementById("modal-logs-content");
  const livePreview = document.getElementById("live-transcription-preview");
  const livePreviewText = document.getElementById("live-transcription-text");
  const apiStatusBadge = document.getElementById("api-status-badge");
  const apiStatusText = document.getElementById("api-status-text");

  // Nomes amigáveis dos ritos
  const riteNames = {
    planning: "🗓️ Sprint Planning",
    daily: "⚡ Daily Check-in (3m)",
    design_review: "🏗️ Design Review (@TL)",
    quality_gate: "🧪 Quality Gate (@QA)",
    sabatina: "🎓 Sabatina EY (@TL)",
    review_star: "🏆 Review XYZ/STAR (@PO)",
  };

  // ==========================================================================
  // INICIALIZAÇÃO
  // ==========================================================================
  async function init() {
    setupSpeechRecognition();
    setupEventListeners();
    await fetchState();

    // Mensagem de boas-vindas do @SM
    triggerRite("planning", true);
  }

  // ==========================================================================
  // CARREGAMENTO DE ESTADO DO SERVIDOR
  // ==========================================================================
  async function fetchState() {
    try {
      const res = await fetch("/api/state");
      const data = await res.json();
      state.agents = data.agents || {};
      state.tasks = data.tasks || [];

      // Atualiza badge de status da API
      if (data.is_gemini_online) {
        apiStatusBadge.className = "badge-status-local badge-status-online";
        apiStatusText.textContent = "Gemini 3.5 Flash Online";
      } else {
        apiStatusBadge.className = "badge-status-local";
        apiStatusText.textContent = "Modo Local (Offline / Demo)";
      }

      renderBoardTasks();
    } catch (err) {
      console.error("Erro ao carregar estado:", err);
    }
  }

  // ==========================================================================
  // RENDERIZAÇÃO DO QUADRO OBSIDIAN (SPRINT ATIVA)
  // ==========================================================================
  function renderBoardTasks() {
    boardTasksContainer.innerHTML = "";

    if (!state.tasks || state.tasks.length === 0) {
      boardTasksContainer.innerHTML = `<div class="task-skeleton">Nenhuma tarefa encontrada.</div>`;
      return;
    }

    state.tasks.forEach((task) => {
      const card = document.createElement("div");
      const isInProgress = task.status === "In Progress";
      card.className = `task-card ${isInProgress ? "active-in-progress" : ""}`;

      let statusClass = "todo";
      if (task.status === "In Progress") statusClass = "in-progress";
      else if (task.status.includes("Review")) statusClass = "code-review";
      else if (task.status === "Done") statusClass = "done";

      card.innerHTML = `
        <div class="task-card-header">
          <span class="task-key-badge">${task.key}</span>
          <select class="status-select ${statusClass}" data-key="${task.key}">
            <option value="To Do" ${task.status === "To Do" ? "selected" : ""}>To Do</option>
            <option value="In Progress" ${task.status === "In Progress" ? "selected" : ""}>In Progress</option>
            <option value="Code Review (@TL)" ${task.status.includes("Review") ? "selected" : ""}>Review (@TL)</option>
            <option value="Done" ${task.status === "Done" ? "selected" : ""}>Done</option>
          </select>
        </div>
        <div class="task-summary">${escapeHtml(task.summary)}</div>
        <div class="task-meta-row">
          <span>⏱️ ${task.estimate}</span>
          <span>🌿 ${task.branch}</span>
        </div>
        <div class="task-dod-box">
          <strong>DoD:</strong> ${escapeHtml(task.dod)}
        </div>
      `;

      // Event listener para mudança de status direto no dropdown
      const select = card.querySelector(".status-select");
      select.addEventListener("change", async (e) => {
        const newStatus = e.target.value;
        await updateTaskStatus(task.key, newStatus);
      });

      boardTasksContainer.appendChild(card);
    });
  }

  async function updateTaskStatus(ticketKey, newStatus) {
    try {
      const res = await fetch("/api/board/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket: ticketKey, status: newStatus }),
      });
      const data = await res.json();
      if (data.success) {
        state.tasks = data.tasks;
        renderBoardTasks();
        appendSystemNotice(`Status da tarefa **${ticketKey}** atualizado para \`${newStatus}\` no Obsidian.`);
      }
    } catch (err) {
      console.error("Erro ao atualizar tarefa:", err);
    }
  }

  // ==========================================================================
  // DISPARO DE RITOS
  // ==========================================================================
  async function triggerRite(riteKey, isAutoInit = false) {
    state.activeRite = riteKey;
    activeRiteName.textContent = riteNames[riteKey] || riteKey;

    // Atualiza botões
    document.querySelectorAll(".rite-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.rite === riteKey);
    });

    // Para qualquer áudio em reprodução (barge-in suave)
    stopAudio();

    const promptText = isAutoInit
      ? "Iniciando o Sprint Planning da Sprint 1"
      : `Iniciando o rito: ${riteNames[riteKey]}`;

    await sendMessageToServer(promptText, state.targetAgent, riteKey);
  }

  // ==========================================================================
  // ENVIO E PROCESSAMENTO DE MENSAGENS
  // ==========================================================================
  async function sendMessageToServer(userText, agentKey = "auto", riteKey = state.activeRite) {
    if (!userText.trim()) return;

    // Se o usuário digitou, mostra a bolha dele
    appendUserMessage(userText);

    // Limpa input
    chatInput.value = "";

    // Para áudio anterior
    stopAudio();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userText,
          agent: agentKey,
          rite: riteKey,
        }),
      });

      const data = await res.json();
      renderAgentResponse(data);

      // Se houver ação no board, sincroniza quadro
      if (data.board_action) {
        await fetchState();
      }
    } catch (err) {
      console.error("Erro no chat:", err);
      appendSystemNotice("Erro ao conectar com a Squad. Verifique o servidor.");
    }
  }

  // ==========================================================================
  // RENDERIZAÇÃO DAS RESPOSTAS DOS AGENTES
  // ==========================================================================
  function renderAgentResponse(data) {
    const card = document.createElement("div");
    card.className = "message-card agent";

    const agentKey = data.agent || "sm";
    const agentAvatar = getAgentAvatar(agentKey);
    const thinkingTagClass = getThinkingClass(data.thinking_level);

    let boardActionHtml = "";
    if (data.board_action && data.board_action.action === "update_status") {
      boardActionHtml = `
        <div class="board-action-badge">
          ✅ Obsidian Atualizado: <strong>${data.board_action.ticket}</strong> &rarr; <code>${data.board_action.new_status}</code>
        </div>
      `;
    }

    // Renderiza o markdown das notas
    let notesRendered = "";
    if (data.markdown_notes) {
      if (window.marked && typeof window.marked.parse === "function") {
        notesRendered = window.marked.parse(data.markdown_notes);
      } else {
        notesRendered = `<pre>${escapeHtml(data.markdown_notes)}</pre>`;
      }
    }

    card.innerHTML = `
      <div class="message-header">
        <span class="message-avatar">${agentAvatar}</span>
        <span class="message-author">${data.agent_name || "Agente"}</span>
        <span class="message-tag-thinking ${thinkingTagClass}">${data.thinking_level || "LOW"}</span>
        <span class="message-time">${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      </div>

      <div class="spoken-bubble">
        <span>${escapeHtml(data.spoken_reply || "")}</span>
        <button class="btn-replay-audio" title="Reouvir áudio">▶️</button>
      </div>

      ${data.markdown_notes ? `<div class="notes-card">${notesRendered}</div>` : ""}
      ${boardActionHtml}
    `;

    // Botão de reouvir
    const replayBtn = card.querySelector(".btn-replay-audio");
    replayBtn.addEventListener("click", () => {
      playAgentAudio(data.spoken_reply, agentKey);
    });

    messagesContainer.appendChild(card);
    scrollToBottom();

    // Sintetiza e toca o áudio imediatamente
    if (data.spoken_reply) {
      playAgentAudio(data.spoken_reply, agentKey);
    }
  }

  function appendUserMessage(text) {
    const card = document.createElement("div");
    card.className = "message-card user";
    card.innerHTML = `
      <div class="message-header" style="justify-content: flex-end;">
        <span class="message-author">Você (Dev)</span>
        <span class="message-time">${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      </div>
      <div class="spoken-bubble user-bubble">
        <span>${escapeHtml(text)}</span>
      </div>
    `;
    messagesContainer.appendChild(card);
    scrollToBottom();
  }

  function appendSystemNotice(text) {
    const div = document.createElement("div");
    div.style.cssText = "font-size: 0.75rem; color: #94a3b8; text-align: center; margin: 4px 0;";
    div.innerHTML = `<em>${text}</em>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
  }

  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  // ==========================================================================
  // SÍNTESE DE VOZ & REPRODUÇÃO (TTS COM BARGE-IN)
  // ==========================================================================
  function playAgentAudio(text, agentKey) {
    stopAudio();

    if (!text) return;

    // Destaca o card do agente que está falando
    setSpeakingAgent(agentKey, true);

    const url = `/api/tts?agent=${encodeURIComponent(agentKey)}&text=${encodeURIComponent(text)}`;
    audioPlayer.src = url;

    audioPlayer.play().catch((err) => {
      console.warn("Reprodução automática bloqueada pelo navegador. Clique para reproduzir:", err);
      setSpeakingAgent(agentKey, false);
    });

    audioPlayer.onended = () => {
      setSpeakingAgent(agentKey, false);
    };

    audioPlayer.onerror = () => {
      setSpeakingAgent(agentKey, false);
    };
  }

  function stopAudio() {
    if (audioPlayer) {
      audioPlayer.pause();
      audioPlayer.currentTime = 0;
    }
    clearSpeakingStatus();
  }

  function setSpeakingAgent(agentKey, isSpeaking) {
    const card = document.getElementById(`agent-card-${agentKey}`);
    if (card) {
      card.classList.toggle("speaking", isSpeaking);
    }
  }

  function clearSpeakingStatus() {
    document.querySelectorAll(".agent-card").forEach((card) => {
      card.classList.remove("speaking");
    });
  }

  // ==========================================================================
  // RECONHECIMENTO DE VOZ (STT NATURA ZERO TOKENS) COM PUSH-TO-TALK
  // ==========================================================================
  function setupSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      console.warn("SpeechRecognition não é suportado nativamente neste navegador. Use o campo de texto.");
      micLabel.textContent = "Mic indisponível";
      btnMic.disabled = true;
      btnMic.title = "Navegador sem suporte a Web Speech API";
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "pt-BR";
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => {
      state.isRecording = true;
      btnMic.classList.add("recording");
      micLabel.textContent = "Ouvindo... (solte para enviar)";
      livePreview.classList.remove("hidden");
      livePreviewText.textContent = "Ouvindo sua voz...";

      // BARGE-IN: Interrompe qualquer áudio em reprodução assim que o dev começa a falar
      stopAudio();
    };

    recognition.onresult = (event) => {
      let interim = "";
      let final = "";

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }

      livePreviewText.textContent = final || interim || "Ouvindo...";
      if (final) {
        chatInput.value = final;
      }
    };

    recognition.onerror = (event) => {
      console.warn("SpeechRecognition erro:", event.error);
      stopRecording();
    };

    recognition.onend = () => {
      stopRecording();
      const transcribed = chatInput.value.trim();
      if (transcribed) {
        sendMessageToServer(transcribed, state.targetAgent, state.activeRite);
      }
    };

    state.recognition = recognition;
  }

  function startRecording() {
    if (state.recognition && !state.isRecording) {
      try {
        chatInput.value = "";
        state.recognition.start();
      } catch (e) {
        console.warn("Erro ao iniciar microfone:", e);
      }
    }
  }

  function stopRecording() {
    state.isRecording = false;
    btnMic.classList.remove("recording");
    micLabel.textContent = "Falar (Espaço ou Clique)";
    livePreview.classList.add("hidden");
  }

  // ==========================================================================
  // EVENT LISTENERS GERAIS
  // ==========================================================================
  function setupEventListeners() {
    // Botões de rito no topo
    document.querySelectorAll(".rite-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        triggerRite(btn.dataset.rite);
      });
    });

    // Seletor de interlocutor
    speakerSelect.addEventListener("change", (e) => {
      state.targetAgent = e.target.value;
    });

    // Clicar em um agente da esquerda seleciona ele no dropdown
    document.querySelectorAll(".agent-card").forEach((card) => {
      card.addEventListener("click", () => {
        const ag = card.dataset.agent;
        speakerSelect.value = ag;
        state.targetAgent = ag;
      });
    });

    // Botão Enviar
    btnSend.addEventListener("click", () => {
      const text = chatInput.value.trim();
      if (text) {
        sendMessageToServer(text, state.targetAgent, state.activeRite);
      }
    });

    // Enter no input
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (text) {
          sendMessageToServer(text, state.targetAgent, state.activeRite);
        }
      }
    });

    // Push-to-Talk via Botão (Mouse e Toque)
    btnMic.addEventListener("mousedown", () => startRecording());
    btnMic.addEventListener("mouseup", () => {
      if (state.recognition && state.isRecording) {
        state.recognition.stop();
      }
    });

    // Push-to-Talk via Teclado (Segurar Barra de Espaço)
    window.addEventListener("keydown", (e) => {
      // Ignora se o usuário está digitando no input de texto
      if (e.target === chatInput) return;

      if (e.code === "Space" && !state.spacePressed && !state.isRecording) {
        state.spacePressed = true;
        e.preventDefault();
        startRecording();
      }
    });

    window.addEventListener("keyup", (e) => {
      if (e.code === "Space" && state.spacePressed) {
        state.spacePressed = false;
        if (state.recognition && state.isRecording) {
          state.recognition.stop();
        }
      }
    });

    // Botão Barge-in
    btnBargein.addEventListener("click", () => {
      stopAudio();
    });

    // Botão Limpar Chat
    btnClearChat.addEventListener("click", () => {
      messagesContainer.innerHTML = "";
    });

    // Recarregar Board
    btnRefreshBoard.addEventListener("click", async () => {
      await fetchState();
    });

    // Modal de Logs do Obsidian
    btnViewLogs.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/state");
        const data = await res.json();
        if (window.marked && typeof window.marked.parse === "function") {
          modalLogsContent.innerHTML = window.marked.parse(data.logs_raw || "Sem registros.");
        } else {
          modalLogsContent.innerHTML = `<pre>${escapeHtml(data.logs_raw || "")}</pre>`;
        }
        logsModal.classList.remove("hidden");
      } catch (err) {
        console.error("Erro ao carregar logs:", err);
      }
    });

    btnCloseModal.addEventListener("click", () => {
      logsModal.classList.add("hidden");
    });

    logsModal.addEventListener("click", (e) => {
      if (e.target === logsModal) {
        logsModal.classList.add("hidden");
      }
    });

    // Botões de Discurso Canônico de Estúdio Gemini (3m HD)
    document.querySelectorAll(".btn-studio-benchmark").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const audioSrc = btn.getAttribute("data-audio");
        const agentKey = btn.getAttribute("data-agent");
        if (!audioSrc) return;

        if (audioPlayer.src && audioPlayer.src.endsWith(audioSrc) && !audioPlayer.paused && !audioPlayer.ended) {
          stopAudio();
          btn.classList.remove("playing");
          return;
        }

        stopAudio();
        document.querySelectorAll(".btn-studio-benchmark").forEach((b) => b.classList.remove("playing"));
        btn.classList.add("playing");
        setSpeakingAgent(agentKey, true);

        audioPlayer.src = audioSrc;
        audioPlayer.play().catch((err) => {
          console.warn("Reprodução bloqueada:", err);
          btn.classList.remove("playing");
          setSpeakingAgent(agentKey, false);
        });

        audioPlayer.onended = () => {
          btn.classList.remove("playing");
          setSpeakingAgent(agentKey, false);
        };
        audioPlayer.onerror = () => {
          btn.classList.remove("playing");
          setSpeakingAgent(agentKey, false);
        };
      });
    });
  }

  // ==========================================================================
  // HELPERS
  // ==========================================================================
  function getAgentAvatar(agentKey) {
    const avatars = {
      sm: "📋",
      tl: "👨‍💻",
      qa: "🧪",
      po: "🎯",
    };
    return avatars[agentKey.toLowerCase()] || "🤖";
  }

  function getThinkingClass(level) {
    if (!level) return "thinking-low";
    if (level.includes("HIGH")) return "thinking-high";
    if (level.includes("MED")) return "thinking-med";
    return "thinking-low";
  }

  function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Inicia aplicação
  init();
});

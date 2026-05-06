# PLAN — Mandarim + Pipeline Improvements (Lotes 1 & 2)

Status: aguardando aprovação. Cada item é uma unidade atômica com teste antes da implementação.

---

## Lote 1 — Mandarim + Quick Wins

### M1 — Adicionar idiomas faltantes ao `language_names` em `gemini_client.py`
- [ ] Em `tests/test_gemini_client_languages.py`, escrever teste pytest que importa o módulo, usa monkeypatch no `genai.Client` e valida que o prompt enviado por `translate_text({...}, 'zh-CN')` contém `"Mandarin Chinese (Simplified)"` (não `"zh-CN"`). Repetir para `nl-NL`, `pl-PL`, `ru-RU`.
- [ ] Refatorar `gemini_client.py`: extrair `LANGUAGE_NAMES` para constante de módulo (top-level), incluir `zh-CN: Mandarin Chinese (Simplified)`, `nl-NL: Dutch`, `pl-PL: Polish`, `ru-RU: Russian`. Atualizar `translate_text()` (linha 145) e `adjust_translation_for_duration()` (linha 472) para usar a constante.
- [ ] Rodar pytest, marcar verde.

### M2 — Recomendação de TTS para Mandarim (estratégia mínima e segura)
- [ ] Em `tests/test_tts_recommendation.py`, escrever teste que importa `Config` e valida `Config.get_recommended_tts_backend('zh-CN') == 'gemini'` e que para `'en-US'` retorna `Config.TTS_BACKEND` (default).
- [ ] Em `config.py`, adicionar `RECOMMENDED_TTS_BACKEND = {'zh-CN': 'gemini'}` (apenas Mandarim por ora) e método `Config.get_recommended_tts_backend(lang)` com fallback ao default.
- [ ] Em `templates/index.html`, adicionar pequeno `<div class="form-text">` no select de TTS engine que muda dinamicamente; em `static/js/app.js` na função `updateVoiceOptions()`, fazer fetch de `/api/tts-recommendation/<lang>` e exibir aviso "Recomendado para este idioma: Gemini TTS" quando aplicável.
- [ ] Em `app.py`, criar endpoint `GET /api/tts-recommendation/<lang>` retornando `{'recommended': 'gemini'}` ou similar.
- [ ] Rodar pytest e validar manualmente no browser que selecionar Mandarim destaca Gemini.

### P2 — Respeitar `Config.TTS_MAX_RETRIES`
- [ ] Em `tests/test_tts_retries.py`, criar teste com `unittest.mock` que monkey-patche `Config.TTS_MAX_RETRIES = 5`, mocka `client.synthesize_speech` para sempre lançar `exceptions.ResourceExhausted`, e valida que `_synthesize_with_retry` é chamado **5 vezes** (não 3).
- [ ] Em `google_tts_client.py:124`, remover parâmetro default `max_retries=3` e usar `Config.TTS_MAX_RETRIES`.
- [ ] Rodar pytest verde.

### V3 — Áudio final com bitrate explícito e estéreo
- [ ] Em `tests/test_video_processor_audio_codec.py`, escrever teste que mocka `ffmpeg.run` (e captura `ffmpeg.output(...)` kwargs via spy), chama `replace_video_audio()` e asserta que `audio_bitrate='192k'` e `ac=2` foram passados.
- [ ] Em `video_processor.py:127-160`, atualizar `replace_video_audio` para usar `audio_bitrate='192k', ac=2, ar=48000`. Adicionar opção env `OUTPUT_AUDIO_BITRATE` (default `192k`) em `config.py`.
- [ ] Rodar pytest verde.

---

## Lote 2 — Performance & Sync

### P1 — Paralelizar geração TTS com semáforo de rate limit
- [ ] Em `tests/test_tts_parallel.py`, criar teste com `unittest.mock` que mocka `synthesize_speech` com `time.sleep(0.5)` simulado. Asserta que `generate_speech` para 10 segmentos completa em **≤ 3s** (5 workers paralelos) e em **≥ 0.5s × 10 = 5s** se single-thread (regressão).
- [ ] Em `google_tts_client.py`, refatorar `generate_speech()`: introduzir `concurrent.futures.ThreadPoolExecutor(max_workers=Config.TTS_PARALLEL_WORKERS)` (default 5), usar `threading.Semaphore` para controlar concorrência, ordenar resultados por `segment_index` ao consolidar lista de retorno. Adicionar `Config.TTS_PARALLEL_WORKERS = int(os.getenv('TTS_PARALLEL_WORKERS', '5'))`.
- [ ] Garantir que mensagens de log mantenham ordem por segmento (loga após `as_completed`).
- [ ] Validar que `_synthesize_with_retry` é thread-safe (não compartilha estado mutável).
- [ ] Rodar pytest verde.

### S1 — Regenerar TTS apenas dos segmentos alterados no loop de duration
- [ ] Em `tests/test_duration_adjustment_targeted.py`, criar teste que mocka `gemini_client.adjust_translation_for_duration` (retorna texto modificado para segmentos 2 e 5) e mocka `google_tts_client.generate_speech_segments(translation_data, voice, dir, segment_indices=...)`. Asserta que após adjustment apenas índices `[2, 5]` foram passados, não `[0..9]`.
- [ ] Em `google_tts_client.py`, adicionar método `generate_speech_segments(translation_data, voice_name, output_dir, segment_indices, model_name)` que gera apenas índices listados (preservando nomes de arquivo `segment_{i:03d}_*.wav`).
- [ ] Em `app.py:607-666`, no loop de duration adjustment: coletar `changed_indices`, chamar `generate_speech_segments` apenas com esses índices em vez de regenerar tudo. Atualizar a lista `audio_files` apenas nas posições alteradas.
- [ ] Rodar pytest verde.

### S2 — Corrigir drift acumulativo em `_fallback_concatenation`
- [ ] Em `tests/test_concat_drift.py`, criar teste com 3 segmentos artificiais (`pcm_s16le`, 24kHz mono, gerados via ffmpeg `anullsrc`/`sine`) onde segmento 0 dura 5s mas timestamp diz 0-3s. Chamar `_fallback_concatenation` e asserta via `ffprobe` que duração final do output é `total_duration` (não maior nem menor que ±0.05s).
- [ ] Em `video_processor.py:170-194`, modificar lógica:
  - Se `current_time > start_time` (overlap): truncar segmento anterior para `target_end = start_time` ANTES de adicionar (gerar arquivo trim temporário); logar warning.
  - Se segmento ultrapassa `total_duration`: truncar para caber.
  - Sempre forçar `current_time = end_time` matematicamente, mesmo após truncate.
- [ ] Rodar pytest verde.

### V1 — Normalização de loudness no áudio final
- [ ] Em `tests/test_loudnorm.py`, criar teste que mocka `subprocess.run` em `video_processor` e chama `_fallback_concatenation`. Asserta que o filtro `loudnorm=I=-16:TP=-1.5:LRA=11` aparece no comando ffmpeg final (e que pode ser desabilitado via `Config.ENABLE_LOUDNORM=False`).
- [ ] Em `config.py`, adicionar `ENABLE_LOUDNORM = os.getenv('ENABLE_LOUDNORM', 'True').lower() == 'true'` e `LOUDNORM_TARGET_I = '-16'`, `LOUDNORM_TP = '-1.5'`, `LOUDNORM_LRA = '11'`.
- [ ] Em `video_processor.py`, adicionar passo de `loudnorm` no comando final do `_fallback_concatenation` (passa via `-af loudnorm=...` no ffmpeg final). Aplicar **uma vez ao final**, não por segmento.
- [ ] Rodar pytest verde.
- [ ] Smoke test manual: rodar `test_fix.py` com `video2-small.mp4` e verificar volume consistente.

---

## Auto-revisão (crítica do plano)

**Riscos identificados:**
1. **TTS paralelo (P1)** pode disparar quotas Vertex se workers > 5. Mitigação: env var `TTS_PARALLEL_WORKERS=5` + manter retry com backoff. Se falhar em produção, reduzir para 3.
2. **Loudnorm single-pass (V1)** é menos preciso que two-pass mas ~10x mais rápido. Aceitável para voiceover. Two-pass adiciona ~30s ao pipeline — não vale.
3. **S1 (regeneração seletiva)** muda o contrato de `generate_speech_segments` — risco de quebrar outras chamadas. Mitigação: manter `generate_speech` como wrapper que chama `generate_speech_segments(indices=range(N))`.
4. **S2 (drift)** pode introduzir clicks audíveis em truncates abruptos. Mitigação: aplicar `afade=t=out:d=0.01` (10ms) no truncate. Adicionar ao item.
5. **Sem framework pytest configurado.** Adicionar `pytest>=7.0` em `requirements.txt` (item zero).
6. **Testes precisam de fixtures de áudio.** Para S2 e V1, gerar arquivos `pcm_s16le` via ffmpeg em `tests/conftest.py` (fixture). Para outros (M1/M2/P1/P2/S1), mocks bastam.

**Adições ao plano após crítica:**
- [x] **Item 0**: Adicionar `pytest>=7.0` ao `requirements.txt` e criar `tests/conftest.py` com fixtures básicas (audio sintético via WAV bytes em Python puro — ffmpeg não está disponível localmente, então testes usam mocks de subprocess/ffmpeg-python).
- [ ] **S2 addendum**: Aplicar `afade=t=out:st={trim_point - 0.01}:d=0.01` no segmento truncado para evitar click.
- [ ] **Commit strategy**: Um commit atômico por item (M1, M2, P2, V3, P1, S1, S2, V1). 8 commits no total + 1 inicial para infra de testes.

**Itens fora de escopo deste plano (deixar para Lote 3):**
- C1-C5 (capacidade): Redis/Firestore, semáforo, SSE, ducking sidechain.
- P3 (sync paralelo) — depende de P1; avaliar após.
- P4 (Files API para vídeo grande) — requer mudança na arquitetura de upload.
- P5 (SSE) — requer refactor frontend completo.

---

## Estimativa
- Lote 1: ~1.5h (M1: 20m, M2: 30m, P2: 15m, V3: 15m + setup tests 10m)
- Lote 2: ~3.5h (P1: 1h, S1: 1h, S2: 45m, V1: 30m + smoke test 15m)
- **Total: ~5h**, 9 commits.

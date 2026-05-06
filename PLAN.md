# PLAN — Mandarim + Pipeline Improvements (Lotes 1 & 2)

Status: aguardando aprovação. Cada item é uma unidade atômica com teste antes da implementação.

---

## Lote 1 — Mandarim + Quick Wins

### M1 — Adicionar idiomas faltantes ao `language_names` em `gemini_client.py`
- [x] Em `tests/test_gemini_client_languages.py`, escrever teste pytest que importa o módulo, usa monkeypatch no `genai.Client` e valida que o prompt enviado por `translate_text({...}, 'zh-CN')` contém `"Mandarin Chinese (Simplified)"` (não `"zh-CN"`). Repetir para `nl-NL`, `pl-PL`, `ru-RU`.
- [x] Refatorar `gemini_client.py`: extrair `LANGUAGE_NAMES` para constante de módulo (top-level), incluir `zh-CN: Mandarin Chinese (Simplified)`, `nl-NL: Dutch`, `pl-PL: Polish`, `ru-RU: Russian`. Atualizar `translate_text()` e `adjust_translation_for_duration()` para usar a constante.
- [x] Rodar pytest, marcar verde (11/11 verdes).

### M2 — Recomendação de TTS para Mandarim (estratégia mínima e segura)
- [x] Em `tests/test_tts_recommendation.py`, testes para Config + endpoint Flask.
- [x] Em `config.py`, adicionado `RECOMMENDED_TTS_BACKEND = {'zh-CN': 'gemini'}` e classmethod `get_recommended_tts_backend()`.
- [x] Em `templates/index.html`, `<div id="tts-backend-help">` agora é alvo dinâmico; em `static/js/app.js`, novo `refreshTTSRecommendation()` é chamado em todo update de idioma/backend.
- [x] Em `app.py`, endpoint `GET /api/tts-recommendation/<lang>` retorna `{language, recommended, is_override}`.
- [x] Pytest 7/7 verdes. Validação manual em browser fica para usuário (ffmpeg não disponível localmente).

### P2 — Respeitar `Config.TTS_MAX_RETRIES`
- [x] Em `tests/test_tts_retries.py`, 3 testes parametrizados: cap=5, sucesso na 3ª, cap=2.
- [x] Em `google_tts_client.py`, `max_retries` agora default a `Config.TTS_MAX_RETRIES` quando `None`.
- [x] Pytest 3/3 verdes.

### V3 — Áudio final com bitrate explícito e estéreo
- [x] Em `tests/test_video_processor_audio_codec.py`, 3 testes capturando kwargs de `ffmpeg.output`.
- [x] Em `video_processor.py`, `replace_video_audio` agora passa `audio_bitrate=Config.OUTPUT_AUDIO_BITRATE`, `ac=2`, `ar=48000`. Adicionado em `config.py`: `OUTPUT_AUDIO_BITRATE` (default `192k`), `OUTPUT_AUDIO_SAMPLE_RATE` (48000), `OUTPUT_AUDIO_CHANNELS` (2).
- [x] Pytest 3/3 verdes.

---

## Lote 2 — Performance & Sync

### P1 — Paralelizar geração TTS com semáforo de rate limit
- [x] Em `tests/test_tts_parallel.py`, 3 testes: timing paralelo (≤1s para 10×0.2s), ordem por índice apesar de scrambling, default de Config.
- [x] Em `google_tts_client.py`, `generate_speech` agora usa `ThreadPoolExecutor(max_workers=Config.TTS_PARALLEL_WORKERS)`. Resultados coletados em dict por índice e re-ordenados.
- [x] `Config.TTS_PARALLEL_WORKERS = 5` (default), env var `TTS_PARALLEL_WORKERS`.
- [x] Pytest 27/27 verdes (sem regressões).

### S1 — Regenerar TTS apenas dos segmentos alterados no loop de duration
- [x] Em `tests/test_targeted_tts_regeneration.py`, 3 testes: subset de índices, delegação do `generate_speech` e índices inválidos ignorados.
- [x] Em `google_tts_client.py`, novo `generate_speech_segments(...)`. `generate_speech` virou wrapper que pede a faixa completa.
- [x] Em `app.py`, loop de duration adjustment agora coleta `changed_indices` e chama `generate_speech_segments` apenas para eles, atualizando `audio_files[idx]` por índice extraído do nome `segment_{idx:03d}_*.wav`.
- [x] Pytest 30/30 verdes (sem regressões).

### S2 — Corrigir drift acumulativo em `_fallback_concatenation`
- [x] Em `tests/test_concat_drift.py`, 3 testes: subprocess trim invocado em segmento que overruns, helper puro `_build_concat_timeline` avança cursor por expected end_time, silêncios só para gaps reais.
- [x] Em `video_processor.py`, extraído `_build_concat_timeline` (puro, testável) e `_get_segment_duration`. `_fallback_concatenation` agora trunca segmentos overrunning com fade-out de 10ms via `_trim_with_fade`, cap em `total_duration`, e cursor sempre = `end_time` esperado (drift = 0).
- [x] Pytest 33/33 verdes.

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

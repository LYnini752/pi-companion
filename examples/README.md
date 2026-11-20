# 测试材料 / Test materials

`prompts.json` 是原创中文合成问题，使用本项目 GPL-3.0 许可，无真实用户数据。

不需要录音即可测试：先启动 `bash scripts/serve_llm.sh`，再运行 `.venv/bin/python scripts/demo.py`。脚本会在本机合成测试提问、识别、回答并生成 `.local/demo/reply.wav`；结果以实际运行文件为准，可能错听。想跳过语音直接试模型，可运行 `.venv/bin/python companion.py --prompt "你好，请用一句话介绍你能做什么。"`。

没有随仓库再分发 HuaYan 音色或其合成录音：该上游音色数据集许可标注 Unknown。只生成你本机的测试文件；来源见 ../THIRD_PARTY.md。

The included Chinese prompts are original synthetic inputs under GPL-3.0. The existing demo script creates a question locally and runs the speech chain without a microphone. Audio is generated locally rather than redistributed because the optional HuaYan voice dataset has unclear licensing. ASR can mishear the question.

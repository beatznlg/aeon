"""
AEON kernel exposed as a Gradio chat endpoint for HF Spaces deployment.

The Vercel frontend's `web/app/api/chat/route.ts` discovers this Space via the
`AEON_HF_SPACE_URL` environment variable and streams responses to the browser
through `@gradio/client`. The Space itself runs on Hugging Face's free tier
(ZeroGPU gives free A100 slices on demand; matches the Colab T4 GPU surface
that AEON was developed against).

To deploy:
  1. Create a new Gradio Space on https://huggingface.co/new-space
  2. Push aeon.py + this file + requirements.txt to the Space
  3. Set HUGGINGFACE_TOKEN as a Space secret (so the Qwen 3-bit download
     succeeds on first request)
  4. Copy the Space URL (e.g. https://beatznlg-aeon.hf.space) and paste it
     as `AEON_HF_SPACE_URL` in the Vercel project's environment variables.
"""

import gradio as gr

from aeon import AeonKernel

kernel = AeonKernel()


def chat_fn(message, history):  # history arg is required by Gradio ChatInterface
    history = history or []
    # AEON's EpisodicStore keeps its own internal state across requests;
    # the `history` list from Gradio is intentionally ignored.
    msg = (message or "").strip()
    if not msg:
        return "(empty message — try asking something)"
    try:
        res = kernel.tick(msg)
    except Exception as e:  # don't let a kernel crash kill the HF Space
        return f"[kernel error: {type(e).__name__}: {e}]"
    return res.get("answer", "") or "[kernel returned empty answer]"


app = gr.ChatInterface(
    fn=chat_fn,
    title="AEON \u03b1 kernel proxy",
    description=(
        "GPU inference endpoint for the AEON Vercel frontend. "
        "POST /chat here from Vercel's @gradio/client."
    ),
    examples=["What is the integral of x^2?", "Compute 1 + 1 + 1", "Solve 2x + 5 = 17"],
    retry_btn=None,
    undo_btn=None,
    clear_btn="Clear",
)


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7860)  #nosec B104

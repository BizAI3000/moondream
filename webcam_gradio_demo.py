import argparse
import torch
import re
import time
import gradio as gr
from moondream import detect_device
from threading import Thread
from transformers import TextIteratorStreamer, AutoTokenizer, AutoModelForCausalLM

parser = argparse.ArgumentParser()
parser.add_argument("--cpu", action="store_true")
args = parser.parse_args()

if args.cpu:
    device = torch.device("cpu")
    dtype = torch.float32
else:
    device, dtype = detect_device()
    if device != torch.device("cpu"):
        print("Using device:", device)
        print("If you run into issues, pass the `--cpu` flag to this script.")
        print()

model_id = "vikhyatk/moondream2"
revision = "2024-03-05"
tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
moondream = AutoModelForCausalLM.from_pretrained(
    model_id, trust_remote_code=True, revision=revision
).to(device=device, dtype=dtype)
moondream.eval()


def answer_question(img, prompt):
    image_embeds = moondream.encode_image(img)
    streamer = TextIteratorStreamer(tokenizer, skip_special_tokens=True)
    thread = Thread(
        target=moondream.answer_question,
        kwargs={
            "image_embeds": image_embeds,
            "question": prompt,
            "tokenizer": tokenizer,
            "streamer": streamer,
        },
    )
    thread.start()

    buffer = ""
    for new_text in streamer:
        clean_text = re.sub("<$|END$", "", new_text)
        buffer += clean_text
        yield buffer.strip("<END")

with gr.Blocks() as demo:
    gr.Markdown("# 🌔 moondream")

    gr.HTML(
        """
        <style type="text/css">
            .md_output p {
                padding-top: 1rem;
                font-size: 1.2rem !important;
            }
        </style>
        """
    )

    with gr.Row():
        prompt = gr.Textbox(
            label="Prompt",
            value="What's going on? Respond with a single sentence.",
            interactive=True,
        )
    with gr.Row():
        img = gr.Image(type="pil", label="Upload an Image", streaming=True)
        output = gr.Markdown(elem_classes=["md_output"])

    latest_img = None
    latest_prompt = prompt.value

    @img.change(inputs=[img])
    def img_change(img):
        global latest_img
        latest_img = img

    @prompt.change(inputs=[prompt])
    def prompt_change(prompt):
        global latest_prompt
        latest_prompt = prompt

    @demo.load(outputs=[output])
    def live_video():
        while True:
            if latest_img is None:
                time.sleep(0.1)
            else:
                for text in answer_question(latest_img, latest_prompt):
                    if len(text) > 0:
                        yield text


demo.queue().launch(debug=True)

import hashlib
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class LlamaServer:
    def __init__(self, url, model, record):
        self.url = url.rstrip("/")
        self.model = model
        self.record = record
        self.alias = f'{model["file"]}@{model["revision"]}'
        props = self.request("/props")
        if props["default_generation_settings"]["n_ctx"] != model["context_tokens"]:
            raise ValueError("llama-server context size differs from baseline.json")
        if props.get("total_slots") != 1 or props.get("model_alias") != self.alias:
            raise ValueError("Use the documented model alias and one llama-server slot")
        build = props.get("build_info", "")
        if not build.startswith(f'{model["llama_cpp_build"]}-'):
            raise ValueError(f"Unexpected llama-server build: {build}")
        record("model_server", alias=self.alias, build=build,
               chat_template_sha256=hashlib.sha256(props["chat_template"].encode()).hexdigest())

    def request(self, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=180) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"{path}: HTTP {error.code}: {error.read().decode()}") from error

    def generate(self, prompt, kind, seed, **context):
        wrapped = self.request("/apply-template", {
            "messages": [{"role": "user", "content": prompt}]
        })["prompt"]
        request = {**self.model["sampling"], "seed": seed, "cache_prompt": False,
                   "n_predict": self.model[f"{kind}_tokens"], "prompt": wrapped,
                   "stop": ["\n"] if kind == "action" else []}
        self.record("model_request", kind=kind, seed=seed, prompt=prompt,
                    prompt_sha256=hashlib.sha256(wrapped.encode()).hexdigest(), **context)
        start = time.perf_counter()
        response = self.request("/completion", request)
        timing = response["timings"]
        self.record("model_response", kind=kind, seed=seed, output=response["content"],
                    input_tokens=response["tokens_evaluated"], output_tokens=response["tokens_predicted"],
                    inference_seconds=(timing["prompt_ms"] + timing["predicted_ms"]) / 1000,
                    request_seconds=time.perf_counter() - start, stop_type=response["stop_type"],
                    truncated=response["truncated"], **context)
        if response["truncated"] or response["model"] != self.alias:
            raise RuntimeError("llama-server changed the context or returned an unexpected model")
        return response["content"].strip()

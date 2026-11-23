from pathlib import Path


ORIGINAL = (Path(__file__).resolve().parents[2] /
            "prompts/reflection_candidates/b_original_instruction.txt").read_text(encoding="utf-8").strip()


def reflection_prompt(query, scenario, memory, instruction):
    """Keep upstream examples, scenario, memory and final cue byte-for-byte."""
    original_query = query(scenario, memory)
    if instruction is None:
        return original_query
    if not original_query.startswith(ORIGINAL + " Here are two examples:"):
        raise ValueError("Unexpected upstream reflection instruction prefix")
    if not instruction.strip():
        raise ValueError("Reflection instruction must not be empty")
    return instruction.strip() + original_query[len(ORIGINAL):]

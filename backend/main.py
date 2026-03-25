from normaliser import normalise_all
from scorer import score_all

def run_pipeline(inputs):
    stage1 = normalise_all(inputs)
    stage2 = score_all(stage1["transactions"])
    return stage2
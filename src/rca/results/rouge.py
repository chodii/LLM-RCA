import os
import statistics

import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

import rca.results.Logger as log


COMPONENTS = {
    "Retrieval": "retrieved",
    "Summarization": "assistant",
    "Final output": "generated",
}

ROUGE_TAGS = ["rouge1", "rouge2", "rougeL"]
MEASUREMENTS = ["precision", "recall", "F1"]


def rouge_results(trans, target_key="reference"):
    """
    Calculate ROUGE scores for one transformed LOGGER.

    Returns:
        {
            "rouge1": {
                "precision": {
                    "Retrieval": [...],
                    ...
                },
                ...
            },
            ...
        }
    """

    result = {}

    for rouge_tag in ROUGE_TAGS:
        result[rouge_tag] = {}

        for measurement in MEASUREMENTS:
            result[rouge_tag][measurement] = {}

            for component, field in COMPONENTS.items():

                values = []

                for i in range(len(trans["generated"])):

                    target = trans[target_key][i]
                    candidate = trans[field][i]

                    score = log.rouge_text(
                        candidate,
                        target,
                        rouge_tag
                    )[rouge_tag]

                    if measurement == "precision":
                        value = score.precision
                    elif measurement == "recall":
                        value = score.recall
                    else:
                        value = score.fmeasure

                    values.append(value)

                result[rouge_tag][measurement][component] = values

    return result

def aggregate_runs(run_results):

    result = {}

    for rouge_tag in ROUGE_TAGS:
        result[rouge_tag] = {}

        for measurement in MEASUREMENTS:
            result[rouge_tag][measurement] = {}

            for component in COMPONENTS:

                max_samples = max(
                    len(run[rouge_tag][measurement][component])
                    for run in run_results
                )

                values = []

                for sample in range(max_samples):

                    sample_scores = [
                        run[rouge_tag][measurement][component][sample]
                        for run in run_results
                        if sample < len(
                            run[rouge_tag][measurement][component]
                        )
                    ]

                    values.append(statistics.mean(sample_scores))

                result[rouge_tag][measurement][component] = values

    return result


def rouge_descriptive_statistics(data):

    for rouge_tag in ROUGE_TAGS:
        for measurement in MEASUREMENTS:

            print()
            print(f"{rouge_tag.upper()} {measurement}")

            for component in COMPONENTS:

                values = data[rouge_tag][measurement][component]

                print(
                    f"{component}: "
                    f"mean={statistics.mean(values):.4f}, "
                    f"median={statistics.median(values):.4f}, "
                    f"sd={statistics.stdev(values):.4f}, "
                    f"min={min(values):.4f}, "
                    f"max={max(values):.4f}"
                )


def test_rouge_components(rouge, rouge_tag, measurement):

    retrieval = rouge[rouge_tag][measurement]["Retrieval"]
    summarization = rouge[rouge_tag][measurement]["Summarization"]
    final = rouge[rouge_tag][measurement]["Final output"]

    comparisons = [
        ("Retrieval", retrieval, "Summarization", summarization),
        ("Summarization", summarization, "Final output", final),
        ("Retrieval", retrieval, "Final output", final),
    ]

    print()
    print(f"{rouge_tag.upper()} {measurement}")

    for name_a, a, name_b, b in comparisons:

        result = wilcoxon(a, b)

        print(
            f"{name_a} vs {name_b}: "
            f"statistic={result.statistic}, "
            f"p={result.pvalue}"
        )


def calc_rouge_stats(outdir, rouge):

    for rouge_tag in ROUGE_TAGS:
        for pp in rouge[rouge_tag]:

            # Boxplot of F1
            data = [
                rouge[rouge_tag][pp]["Retrieval"],
                rouge[rouge_tag][pp]["Summarization"],
                rouge[rouge_tag][pp]["Final output"],
            ]

            plt.figure()

            plt.boxplot(
                data,
                tick_labels=[
                    "Retrieval",
                    "Summarization",
                    "Final output"
                ]
            )

            plt.ylabel(f"{rouge_tag.upper()} {pp}")
            plt.title(f"{rouge_tag.upper()} {pp} against reference RCA")

            plt.savefig(
                os.path.join(
                    outdir,
                    f"{rouge_tag}-{pp}-reference.pdf"
                ),
                bbox_inches="tight"
            )

            plt.close()
            # PCP
            data = {
                    "Retriever": rouge[rouge_tag][pp]["Retrieval"],
                    "Summaries": rouge[rouge_tag][pp]["Summarization"],
                    "Final output": rouge[rouge_tag][pp]["Final output"]
            }
            log.plot_pcp(
                lines = data
                , axes = list(data.keys())
                , normalize=False,
                title=f"{rouge_tag.upper()} {pp} - reference RCA",
                dest=outdir
            )


def rouge_analysis(paths, dest, target_key="reference"):

    os.makedirs(dest, exist_ok=True)

    # Transform each LOGGER exactly once.
    run_results = []

    for path in paths:
        trans = log.transform(path)
        run_results.append(
            rouge_results(trans, target_key)
        )

    # Average repeated runs sample-wise.
    rouge = aggregate_runs(run_results)

    # Descriptive statistics.
    rouge_descriptive_statistics(rouge)

    # Statistical comparisons.
    for rouge_tag in ROUGE_TAGS:
        for measurement in MEASUREMENTS:
            test_rouge_components(
                rouge,
                rouge_tag,
                measurement
            )

    # Plots.
    calc_rouge_stats(dest, rouge)
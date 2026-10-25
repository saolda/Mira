# Research: What theoretical justification, empirical results and limitations are reported for dropout in recurrent neural

```json
{
  "id": "r1",
  "metadata": {
    "created_order": 1,
    "evidence_ref": "research/results/30b05e6155894e918f191ac3e0a8345b.json",
    "kind": "research",
    "node_id": "q1",
    "source_memories": [],
    "synthesized_by": null
  },
  "next": {
    "e": 1,
    "f": 5,
    "q": 1
  },
  "revision": 1,
  "summary": "Standard dropout fails when applied to recurrent layers in RNNs, contributing to their tendency to overfit.",
  "version": 1
}
```

## Memory

[#f1] Standard dropout fails when applied to recurrent layers in RNNs, contributing to their tendency to overfit.

**Kind:** finding

**Evidence status:** unverified

**Proposition:** Standard dropout fails when applied to recurrent layers in RNNs, contributing to their tendency to overfit.

**Explanation:** This is presented as a known difficulty with RNNs prior to the proposed method.

**Provenance:** Supplied source identifiers: http://arxiv.org/abs/1512.05287v5. Model extraction; not independently verified.

[#f2] A variational inference based dropout technique, grounded in a Bayesian interpretation of deep learning, provi

**Kind:** finding

**Evidence status:** unverified

**Proposition:** A variational inference based dropout technique, grounded in a Bayesian interpretation of deep learning, provides a theoretical justification for using dropout in RNNs.

**Explanation:** The approach extends theoretical results from approximate Bayesian inference.

**Provenance:** Supplied source identifiers: http://arxiv.org/abs/1512.05287v5. Model extraction; not independently verified.

[#f3] The proposed variational inference based dropout technique outperforms existing techniques in LSTM and GRU mod

**Kind:** finding

**Evidence status:** unverified

**Proposition:** The proposed variational inference based dropout technique outperforms existing techniques in LSTM and GRU models.

**Explanation:** Assessed on language modelling and sentiment analysis tasks.

**Provenance:** Supplied source identifiers: http://arxiv.org/abs/1512.05287v5. Model extraction; not independently verified.

[#f4] The method improves on the single model state-of-the-art in language modelling with the Penn Treebank dataset,

**Kind:** finding

**Evidence status:** unverified

**Proposition:** The method improves on the single model state-of-the-art in language modelling with the Penn Treebank dataset, achieving a test perplexity of 73.4.

**Explanation:** Reported as the best of the authors' knowledge at the time of publication.

**Provenance:** Supplied source identifiers: http://arxiv.org/abs/1512.05287v5. Model extraction; not independently verified.

## Relationships

```json
{
  "relationships": [
    {
      "from": "f1",
      "status": "unverified",
      "to": "http://arxiv.org/abs/1512.05287v5",
      "type": "CITES"
    },
    {
      "from": "f2",
      "status": "unverified",
      "to": "http://arxiv.org/abs/1512.05287v5",
      "type": "CITES"
    },
    {
      "from": "f3",
      "status": "unverified",
      "to": "http://arxiv.org/abs/1512.05287v5",
      "type": "CITES"
    },
    {
      "from": "f4",
      "status": "unverified",
      "to": "http://arxiv.org/abs/1512.05287v5",
      "type": "CITES"
    }
  ],
  "version": 1
}
```

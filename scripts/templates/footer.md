## Contributing

Know a looped model for medical imaging that belongs here, or spotted a wrong link? Contributions are very welcome.

> [!TIP]
> **Quickest:** open an issue with the [**Add a paper**](../../issues/new?template=add-paper.yml) template.<br>
> **Pull request:** add a row to [`data/papers.csv`](data/papers.csv) with an approved `taxonomy_class` and `taxonomy_subcategory`, then run `python scripts/build_readme.py`.

> [!IMPORTANT]
> Never edit this README by hand. It is generated from the CSV, and the next build overwrites manual changes. To change the intro or footer, edit [`scripts/templates/`](scripts/templates).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the column definitions and the [classification guide](docs/classification-guide.md) for the taxonomy rules. The taxonomy itself only changes through a maintainer-approved update to [`config/taxonomy.json`](config/taxonomy.json) that follows the survey's Figure 3. How each of the survey's 56 records was imported is documented in the [initial import report](docs/initial-import-report.md).

## Citation

If this list helps your research, please cite the survey:

```bibtex
@misc{saswato2026looped,
  title  = {Looped Models for Medical Imaging: A Survey of Iterative Architectures, Test-Time Adaptation, and Feedback},
  author = {Saswato, Aritra Islam and Karim, Labiba Faiza and Khan, Md. Misbah and Khan, Nishan and Ahmed, Istiak and
            Ahmed, Galib and Sanjid, Kazi Shahriar and Hossain, Md. Tanzim and Uddin, M. Monir},
  year   = {2026},
  note   = {Preprint, October 2026}
}
```

GitHub's **Cite this repository** button gives a citation for the list itself ([`CITATION.cff`](CITATION.cff)).

## License

[![CC0](https://licensebuttons.net/p/zero/1.0/88x31.png)](https://creativecommons.org/publicdomain/zero/1.0/)

To the extent possible under law, the contributors have waived all copyright and related rights to this list. Each listed paper and code repository remains under its own license.

<div align="center">
<br>
<sub>Maintained by the <a href="https://github.com/Big-Matrix-R-And-D-Lab">Big-Matrix R&amp;D Lab</a>, North South University. If this list is useful, a ⭐ helps others find it.</sub>
</div>

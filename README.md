# Photo Time Stamper

*[中文](./README-zh.md)*

![Software icon, generated using NanoBananaPro](assets/readme-logo.png)

`Photo Time Stamper` (`photo-timestamper`) is a simple desktop application for adding **camera OEM-style** timestamp watermarks to photos.

![Example image using `Canon` preset](./assets/demo.png)

*Built with PyQt WebEngine and open-sourced on [GitHub](https://github.com/Water-Run/photo-timestamper).*

***[Download](https://github.com/Water-Run/photo-timestamper/releases/tag/1.0)*** `photo-timestamper-[your-system].zip`, extract it, then run `install.bat` (Windows) or `install.sh` to install.

## Watermark Styles

`Photo Time Stamper` includes multiple built-in watermark presets that match camera OEM styles:

- `CANON`

- `NIKON`

- `SONY`

- `PANASONIC`

- `FUJIFILM`

- `PENTAX`

- `XIAOMI`

- `CLASSIC-FILM`

> You can add or modify presets by placing a spec-compliant `YML` file under `style/`. Uses [SimpSave](https://github.com/Water-Run/SimpSave/tree/master/source) for formatted storage, with the database named `English&Chinese`.

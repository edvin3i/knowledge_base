---
tags:
  - 3d-printing
  - hardware
  - bambulab
created: 2026-02-04
---

# Bambu Lab H2D

## Что это

3D-принтер от Bambu Lab серии H2.

## Проблемы и решения

### Сопло царапает модель при печати

**Симптомы:**
- Сопло царапает поверхность модели во время печати
- Слышен характерный звук при быстром перемещении над поверхностью
- "Волосы" и царапины на модели
- Иногда модель сдвигается с места или отрывается от стола

**Причина:**
Настройка **"Reduce infill retraction"** в Bambu Studio связывает Z-hop с ретрактом. Когда печатается инфилл без ретракта, Z-hop тоже отключается, и сопло царапает уже напечатанные поверхности.

**Решения:**

1. **Отключить "Reduce infill retraction"** (главное решение)
   - Bambu Studio: Quality → Other → Reduce infill retraction → **отключить**
   - Это заставит сопло всегда подниматься при перемещениях

2. **Настроить Z-hop**
   - Установить Z-hop на 0.4-0.6mm
   - Путь: Quality → Travel → Lift height (Z-hop)

3. **Сменить паттерн заполнения**
   - Избегать Grid и Triangles — они имеют пересечения в одном слое
   - Использовать **Gyroid** или **Honeycomb** — у них нет пересекающихся линий

4. **Механические проверки**
   - Проверить крепление хотенда (hotend clip) — может быть ослаблено
   - Выполнить ручную калибровку стола
   - Проверить Z-offset

5. **Настройки температуры**
   - Если температура сопла слишком низкая, пластик не течёт нормально и залипает
   - Попробовать увеличить температуру на 5-10°C

### Ресурсы

- [H2D scratches over Infill - Bambu Lab Forum](https://forum.bambulab.com/t/h2d-scratches-over-infill/164331)
- [How to fix nozzle scratching model during print](https://forum.bambulab.com/t/how-to-fix-nozzle-scratching-model-during-print/89104)
- [H2D Toolhead Scraping - Bambu Lab Wiki](https://wiki.bambulab.com/en/h2/troubleshooting/toolhead-scraping-the-build-surface)
- [Common print quality problems - Bambu Lab Wiki](https://wiki.bambulab.com/en/knowledge-sharing/common-print-quality-problem)
- [Zoffset? Scratching Nozzle - Bambu Lab Forum](https://forum.bambulab.com/t/zoffset-scratching-nozzle-need-help/27465)

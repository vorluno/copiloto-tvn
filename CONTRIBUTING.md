# Cómo trabajar en el repo y abrir un PR

Guía corta para Levi y Cristian (y cualquier sesión de Claude Code). Las reglas completas
están en [`CLAUDE.md`](CLAUDE.md) y las tareas en [`docs/backlog.md`](docs/backlog.md).

## 1. Una sola vez

```bash
git clone https://github.com/vorluno/copiloto-tvn.git
cd copiloto-tvn
make setup      # Python 3.11 → .venv, dependencias fijadas, copia .env.example a .env
make test       # deben pasar las pruebas de contrato; T01–T10 salen en "skipped"
make demo       # abre la app en http://localhost:8501 con los datos sintéticos
```

- Necesitas **Python 3.11** y `make`. En Windows, usa WSL.
- `.env`: solo quien llama al LLM necesita `LLM_API_KEY` (OpenRouter). Para datos (Levi) y
  frontend con el stub (Cristian) no hace falta. **Nunca** pegues una clave en el código, en
  Notion, en un PR ni en un chat.

## 2. Por cada tarea

```bash
git checkout main && git pull
git checkout -b feat/B-03-worldbank          # feat/<ID>-<slug>; documentación: docs/<ID>-<slug>
# ... trabajas ...
make test                                    # verde antes de subir
git add <archivos>
git commit -m "B-03: cuadrícula del Banco Mundial con nulos explícitos"
git push -u origin feat/B-03-worldbank
```

Luego abre el PR en GitHub hacia `main`. La plantilla te pide el ID de la tarea y una lista corta
de comprobación. **José revisa y hace merge**; nadie hace merge de su propio PR ni sube directo a `main`.

## 3. Reglas que más se rompen

- **El ID de la tarea va en la rama y en cada commit.** Cristian enlaza los commits desde Notion.
- **PR chico:** una tarea, idealmente menos de 300 líneas. Si crece, se parte.
- **Contratos:** si tu cambio agrega, quita o renombra una columna de un archivo de `CLAUDE.md` §3,
  avisa en la sincronización **antes** y actualiza el stub y su prueba en el mismo PR.
- **Solo tus archivos:** cada carpeta tiene dueño (README → "Estructura del repo"). Si necesitas
  tocar algo de otro, avísale primero.
- **Nulos como nulos, fechas en UTC, nada inventado.** Los datos sintéticos llevan `sintetico=true`.
- **Datos crudos (`data/raw/`) y caché (`outputs/cache/`) no se suben:** están en `.gitignore`.
- **Una prueba que falla no se borra:** se arregla, y Cristian anota el fallo y la corrección en la
  matriz T01–T10. Para implementar una prueba T0x, quita su `pytest.mark.skip` en tu PR.
- **Cada decisión técnica** (modelo de embeddings, umbral, regla de contexto, diseño de una pantalla)
  se le dicta a Cristian para "Plan y decisiones" en Notion el mismo día.

## 4. Si usas Claude Code

Abre la sesión en la raíz del repo: `CLAUDE.md` se carga solo. Pídele que trabaje en la rama de tu
tarea y que corra `make test` antes de hacer commit.

# TBH Save Editor — Editor de Encantamentos

App web local (roda no navegador) para editar os **encantamentos** (decoration / engraving /
inscription) dos itens equipados dos heróis no save do **Taskbar Hero**, com **validação pelas
tabelas reais do jogo** e **recálculo automático do `SystemInfo`** (a proteção anti-tamper) ao salvar.

## Como usar (na máquina onde você joga)

Pré-requisito: **Python 3** instalado. Nada além disso — sem `pip install`.

```
cd saveEditor
python server.py
```

Abre `http://127.0.0.1:8765` no navegador. Então:

1. O caminho do `SaveFile_Live.es3` já vem preenchido (auto-detectado). Clique **Carregar**.
2. Escolha um **herói** → veja os **itens equipados** (ícone + nome traduzido).
3. Clique num **item** → painel de **encantamentos** (2 Decoration, 2 Engraving, 2 Inscription).
4. **Editar/Adicionar** um slot: escolha o **material** → o **stat** (as opções válidas para o
   tipo de equipamento) → o **tier** → o **valor** (dentro do range; botão **Máx**). Só valores
   coerentes são aceitos.
5. **Salvar no jogo** grava o `.es3` (com backup `.es3.bak`) e recalcula o `SystemInfo`.

> **Feche o jogo antes de salvar** — senão ele sobrescreve o arquivo ao sair.

## Estrutura

```
saveEditor/
  server.py          # servidor web local (stdlib, zero deps)
  core/
    es3.py           # decripta/encripta o .es3 + recalcula o SystemInfo (HMAC)
    aes_pure.py      # AES-128 em Python puro (fallback sem dependencias)
    gamedata.py      # tabelas do jogo + validacao de encantamentos
  web/               # interface (HTML/CSS/JS)
  data/              # dados extraidos do jogo (portavel; vai junto com a app)
    tables/*.csv     # StatModInfoData, MaterialInfoData, StatModGroupInfoData, GradeInfoData...
    names_en.json / names_pt.json   # nomes traduzidos por ItemKey
    enums.json       # StatType / MODTYPE / ERecipeType / EMaterialType / EGradeType
    icons/*.png      # icones dos itens/materiais
  extract/           # scripts que GERAM data/ (rodam 1x, requerem UnityPy)
```

## Re-extrair dados (quando o jogo atualizar)

Os dados em `data/` foram extraídos da versão **1.00.17**. Se o jogo atualizar e os valores
mudarem, re-extraia (numa máquina com o jogo + `pip install UnityPy`):

```
python extract/extract_all.py
```

Se uma atualização trocar a **chave HMAC** do `SystemInfo`, atualize `SYSTEMINFO_HMAC_KEY`
em `core/es3.py` (extraível em runtime via o `dtcore.dll`, hotkey F8).

## Como funciona a validação

`material → MaterialInfoData (tipo + grupo) → StatModGroupInfoData (StatModKey + tier por GearGroup)
→ StatModInfoData (StatType, ModType, range de Value por tier)`. O GearGroup do item
(WEAPON/ARMOR/ACCESSORY) sai da faixa do ItemKey. O editor só permite combinações que existem
no jogo, então os encantamentos resultantes são legítimos.

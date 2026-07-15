# Plan: PicoRV32/Tang Nano 9K target za atome-lm

Cilj: novi `c_engine/targets/picorv32-tangnano9k/` target za
[TilelliLab/atome-lm](https://github.com/TilelliLab/atome-lm), koji portuje
njihov C99 ternary inference engine na PicoRV32 RISC-V soft-core na Tang Nano
9K FPGA. Infrastruktura (UART platform layer, PicoRV32 toolchain, Gowin EDA
tok) se **preuzima kao tehnička referenca** iz `FreeRTOS-TetriSaraj` projekta,
ali se taj projekat ne dira niti mijenja — sav novi kod ide u atome-lm fork.

Ovaj plan je pisan nakon provjere stvarnih memory budžeta u tvom PicoRV32
hardveru (ne pretpostavki) i stvarnih memory zahtjeva atome-lm-a iz njihovog
`RAM_TABLE.md`. Nalaz mijenja plan: prva faza mora biti mjerenje, ne pisanje
firmware koda.

## 0. Verdikt unaprijed

**AŽURIRANO nakon Faze 0 (stvarna kompilacija/link, ne procjena):
originalni verdikt ispod je bio pogrešan. Flash se uklapa sa dobrom
marginom (40% na `rv32imc`, 53% na `rv32im`); RAM je stvarno tijesan
(88%), ali stane.** Pun nalaz, brojevi i uzrok greške u prvobitnoj
procjeni: [`c_engine/targets/picorv32-tangnano9k/README.md`](c_engine/targets/picorv32-tangnano9k/README.md#faza-0-mjerenje--originalni-verdikt-plana-je-bio-pogrešan).
Ukratko: 41.9 KB flash brojka iz `RAM_TABLE.md` dolazi sa Cortex-M3
build-a koji linkuje `-lc -lrdimon -lm` (puni semihosting + newlib) —
nešto što ovaj bare-metal UART target nikad nije trebao. Kad se
umjesto toga koriste ručno pisani `memcpy`/`memset`/`memcmp`/`errno`
(vidi `libc_stubs.c`) i `-lm -lgcc` bez `-lc`, stvarni RISC-V build
stane u budžet. Faza 1 (BSRAM resinteza) nije potrebna za `nano`/`tiny`
config. Originalno obrazloženje ispod je ostavljeno radi konteksta —
vidi README za tačne izmjerene brojeve.

## 1. Tvrda tehnička osnova

### 1.1 Tvoj HW memory map je DVA odvojena BRAM regiona, ne jedan

| Region | Fajl / parametar | Stvarna veličina | Za šta |
|---|---|---|---|
| "Flash" / progmem | `progmem.v`: `MEM_SIZE_BITS = 13` → 8192 riječi | **32 KB** | `.text` + `.rodata`, pečeno u bitstream preko `progmem.py` iz `.bin`-a |
| Data RAM | `picosoc_noflash.v`: `MEM_WORDS = 4096` | **16 KB** | `.data` + `.bss` + heap + stack |

Bitno: `2.sw/main.lds` deklariše RAM regiju od 32 KB (`LENGTH = 0x8000`) — to
je **zastarjelo**, ne odgovara stvarno instanciranom hardveru
(`4*MEM_WORDS = 0x4000` = 16 KB). Linker script laže; RTL je istina. Za novi
target treba nov linker script sa tačnim brojevima, ne kopija `main.lds`.

`top.v` i `top_uart_hello.v` instanciraju `picosoc_noflash` bez override-a
(default `MEM_WORDS=4096`, `COMPRESSED_ISA=1`). Samo `top_freertos_game.v`
(HDMI+FreeRTOS kombo) mijenja parametre radi BRAM/LUT pritiska od video
front-enda — to ovdje nije relevantno jer koristimo plain UART-only top.

### 1.2 atome-lm-ovi zvanični memory zahtjevi

Iz `c_engine/RAM_TABLE.md` (generisan `scripts/measure_ram.py` na stvarnom
Cortex-M3 buildu), najmanji zvanični config (`nano`/`tiny`: d_model=16,
layers=2, max_seq=32):

| | Flash (.text+.data+model) | RAM (.bss) | Stack | Peak RAM |
|---|---|---|---|---|
| nano/tiny | **41.9 KB** | 14.3 KB | 144 B | **14.5 KB** |

Naspram tvog budžeta:
- RAM: 14.5 KB od 16 KB → **stane, margina ~1.5 KB** za stack + sve ostalo.
- Flash/progmem: 41.9 KB od **32 KB** → **ne stane, fali ~10 KB (31% preko)**,
  i to je već najmanji config koji atome-lm nudi.

### 1.3 Skriveni rizik — float bez FPU

`atome_state_t` je sav u `float` (aktivacije, LayerNorm, softmax); čak i
`atome_ternary_matvec` (bez float-multiply-a) radi float add/sub. PicoRV32
nema F-extension — tvoj `MARCH ?= rv32im` to potvrđuje. GCC će generisati
pozive u softfloat rutine iz `libgcc` (add/sub/cmp), i vjerovatno treba
`sqrtf` za LayerNorm normalizaciju. Tvoj postojeći `CFLAGS` ima `-nostdlib
-nostartfiles -fno-builtin` — isključuje libgcc ako se eksplicitno ne doda
nazad. Ovo mora ući u Fazu 0 mjerenje (softfloat rutine nose nekoliko KB
koda), sa odlukom: linkovati `-lgcc` (+ eventualno ručno napisan mali
`sqrtf` da se izbjegne pun libm, u duhu atome-lm-ove "zero-dependency"
filozofije).

### 1.4 Reprogramiranje i toolchain

- `progmem.py` peče `.bin` direktno u Verilog `initial` blok — svaka promjena
  firmware-a znači ponovnu Gowin sintezu (`make bitstream` →
  `openFPGALoader`), ne live UART reflash. `2.sw/program.py` je odvojen,
  izgleda kao stariji/alternativni put; plan se na njega ne oslanja.
- Default `MARCH=rv32im` (bez C-extension), ali `COMPRESSED_ISA=1` je
  hardverski dostupan na plain topu — dakle `rv32imc` je poluga za smanjenje
  koda (~20-30% tipično) koju treba iskoristiti.

## 2. Dizajn odluke (i šta je odbačeno)

- **HW baza: `top_uart_hello.v` / `build.tcl`** (čisti UART-only top), ne
  FreeRTOS+HDMI game top. Nema video/HDMI BRAM potrošnje ovdje. *Odbačeno:*
  FreeRTOS varijanta — krade RAM/stack budžet koji je već na ivici, bez
  koristi za single-threaded inference loop.
- **Bare-metal**, kao `hello.c`/`timer_hello.c` pattern, ne FreeRTOS task.
- **UART I/O reuse:** tvoj postojeći `2.sw/uart.c`/`uart.h`
  (`putchar`/`print`/`print_hex`) umjesto atome-lm cortex-m3 targeta koji
  koristi semihosting printf.
- **Model config:** `nano`/`tiny` kao polazna tačka, sa spremnošću da se ide
  i manje (npr. `ATOME_MAX_SEQ=16` umjesto 32) ako Faza 0 pokaže da treba.
- ~~`rv32imc` umjesto `rv32im`~~ — **OBOREN u Fazi 5, na stvarnom hardveru.**
  `rv32imc` firmware veći od ~8 KB progmem-a tiho ne daje NIKAKAV UART izlaz na
  ovoj tačnoj `progmem.v`/`picosoc_noflash.v` kombinaciji — potvrđeno biselekcijom
  na stvarnoj ploči (firmware bez ijedne linije atome/libm/libgcc koda, samo
  padding niz, radi na `rv32im`, ćuti na `rv32imc`, ista veličina). `rv32im`
  je sada default. Pun nalaz: [`hardware/tangnano9k/README.md`](hardware/tangnano9k/README.md).
- **FreeRTOS-TetriSaraj repo ostaje netaknut, read-only referenca.** Sav novi
  kod ide u fork `atome-lm`-a kao `c_engine/targets/picorv32-tangnano9k/`;
  UART driver/linker-pattern se adaptira (kopira i mijenja), ne referencira
  submodulom niti mijenja original.

## 3. Fazni plan

### Faza 0 — Mjerenje, prije bilo kakvog HW rada

Clone fork atome-lm-a, kompajlirati `atome.c` + `nano`/`tiny` config sa
`riscv64-unknown-elf-gcc -march=rv32im -mabi=ilp32 -Os -ffreestanding
-nostdlib -c` (i posebno sa `rv32imc`), pogledati `size` output za
`.text+.rodata`, plus stvarnu veličinu weight blob-a. Provjeriti da li repo
ima gotov `nano`/`tiny` checkpoint ili treba placeholder iste veličine.
Izmjeriti koliko dodaje `-lgcc` (softfloat).

**Izlaz:** konkretan izmjeren broj naspram 32 KB budžeta — ne procjena.

### Faza 1 — Opciono, samo ako Faza 0 pokaže da treba više prostora

Provjeriti u Gowin sintezi (`tang_nano_9k_uart_hello.gprj`) koliko BSRAM-a je
trenutno slobodno. Ako ima mjesta: `MEM_SIZE_BITS` 13→14 u kopiji
`progmem.v` (32→64 KB) i/ili `MEM_WORDS` u kopiji `picosoc_noflash.v`. Ovo je
kopija unutar novog targeta, original TetriSaraj fajlovi se ne diraju.

### Faza 2 — Struktura

```
c_engine/targets/picorv32-tangnano9k/
  README.md
  Makefile
  linker.ld        (nov, sa TAČNIM 32K/16K granicama, ne main.lds kopija)
  start.s           (adaptirano od tvog start.s)
  uart.c / uart.h   (adaptirano od tvog uart.c)
  firmware.c        (glue: atome_load -> atome_init -> generate loop -> UART print)
```

### Faza 3 — Firmware glue kod

`firmware.c` po uzoru na cortex-m3 target (load→init→predict→print logits),
sa zamjenom semihosting-a tvojim `uart_puts`/`print_hex`. `start.s` reuse-ovan
uz provjeru gdje se inicijalizuje `sp` (PicoRV32 ga postavlja na
`STACKADDR` hardverski na reset).

### Faza 4 — Build sistem

Nov Makefile po uzoru na cortex-m3 target, ali sa tvojim postojećim
flagovima (`-Os -ffreestanding -nostdlib -nostartfiles -fno-builtin
-march=rv32imc -mabi=ilp32`) + eksplicitan `-lgcc` (i po potrebi ručni
`sqrtf`).

### Faza 5 — Verifikacija — ZAVRŠENA na stvarnom hardveru

Ploča je bila povezana (FT2232, SIPEED FactoryAIOT Pro JTAG Debugger,
`/dev/ttyUSB1`=UART/`/dev/ttyUSB0`=JTAG), Gowin EDA i `openFPGALoader` su bili
lokalno instalirani. Urađeno:

1. Kopiran HW projekat (ne referenciran) iz FreeRTOS-TetriSaraj u
   `hardware/tangnano9k/firmware/` — `top_uart_hello.v`, `progmem.v`
   (regeneriše se), `picosoc_noflash.v`, `picorv32.v`, `simpleuart.v`,
   constraints, `build.tcl`, `progmem.py`. Original netaknut.
2. `firmware.bin` upečen u `progmem.v` preko `progmem.py`.
3. Headless Gowin sinteza (`gw_sh build.tcl`, env recept iz
   FreeRTOS-TetriSaraj-ovog `0.doc/milestone_0_1_uart_hello.md`) — bitstream
   generisan bez timing grešaka.
4. `openFPGALoader -b tangnano9k` flash na SRAM (volatile, reverzibilno) —
   CRC uspio.
5. Stvaran UART izlaz uhvaćen (pyserial, 115200 8N1) — **radi**, vidi
   `hardware/tangnano9k/evidence/serial_boot_log_tangnano9k.txt`.

Usput otkriveno i popravljeno, sve na stvarnom hardveru (ne u simulaciji):

- **`uart.c` nikad nije postavljao UART clock divider** (registar na
  `0x02000004`). Hardverski POR default (562) daje ~48 KBd, ne 115200 —
  ispravno je 234 (potvrđeno u FreeRTOS-TetriSaraj-ovom vlastitom
  `milestone_0_1_uart_hello.md`). Dodano `uart_init()`.
- **`rv32imc` tiho ne radi preko ~8 KB progmem-a** — najveći nalaz cijele
  faze, obara dizajn odluku iz sekcije 2. Vidi gore i
  `hardware/tangnano9k/README.md` za punu biselekciju.
- `ENTRY(start)` + `KEEP(*(.text.start))` dodano u `linker.ld` kao odbrambena
  mjera (nije bio stvarni uzrok bug-a, ali je dobra praksa uz `--gc-sections`).

Cross-compile dio (sintaksa, `size` unutar budžeta) je pokriven kroz Fazu 0.
Parity test protiv Python reference **nije urađen** — nema pravog treniranog
`nano`/`tiny` checkpoint-a u repou (samo placeholder generator), pa trenutni
HW izlaz namjerno nije smislen tekst, samo dokaz da engine radi na silicijumu.

### Faza 6 — PR

Prati CONTRIBUTING.md šablon (nov folder pod `c_engine/targets/`, ne dirati
`c_engine/upstream/`), README sa izmjerenim brojevima (RAM/Flash usage,
eventualno cycles/token), isti stil kao ESP32-ov evidence folder.

## 4. Glavni otvoreni rizici (po prioritetu) — STANJE NAKON FAZE 0

1. ~~41.9 KB > 32 KB progmem budžet~~ — **RIJEŠENO, bilo pogrešno.** Stvarni
   RV32 build (bez `-lc`, sa `--gc-sections`) je 13.1 KB (`rv32imc`) / 17.5 KB
   (`rv32im`) — 40%/53% od 32 KB. 41.9 KB je bio Cortex-M3 broj naduvan
   semihosting/newlib linkovanjem koje ovaj target ne koristi.
2. ~~RAM margina nepotvrđena~~ — **IZMJERENO direktno na hardveru, ne
   procjenom.** `firmware_ramcheck.elf` (stack-painting tehnika, ista kao
   `cortex-m3-ram/firmware.c`) je flash-ovan i pokrenut na stvarnoj ploči:
   `bss=14452 B, stack_used=304 B, total=14756/16384 B (90.1%), margina=1628
   B slobodno`. Realan stack trošak je ~2× Cortex-M3-ovih 144 B (RV32
   calling convention, više registara za spill), ali margina i dalje drži.
   Dokaz: `hardware/tangnano9k/evidence/serial_ramcheck_log_tangnano9k.txt`.
   Ako ikad zatreba više prostora, `ATOME_MAX_SEQ=16` daje dodatan prostor.
3. **Faza 1 (BSRAM resinteza) nije potrebna** — flash margina je dovoljna
   bez nje za `nano`/`tiny` config.
4. **Softfloat troškovi izmjereni**: libgcc (add/sub/mul/div/compare) ~5.0
   KB; `sqrtf`+`expf`+`tanhf` (+ njihove interne `expm1f`/CLZ tabele) ~2.6
   KB dodatno. ~7.6 KB ukupno, 40-60% od `.text` zavisno od `march`-a — realan
   trošak, ali stane, pa ručno pisane float rutine nisu bile potrebne.

5. **Novo, treće: pravi bug, ali u upstream `atome.c`, ne u ovom targetu.**
   Nakon što je NULL-pointer bug (ispod) popravljen, prava inferenca je
   prvi put stvarno počela da radi na hardveru — i zaglavila se. Bisekcija
   pomoću privremene instrumentirane lokalne kopije `atome.c` (nije
   commit-ovana) pokazala je: `atome_load()`-ov binarni parser proizvodi
   NEPORAVNATE `float*` pokazivače (`gamma_addr=0x001042DB`, `0xDB mod 4 =
   3`) — potiče iz 7-bajtnog `"ATOME01"` magic stringa (`7 mod 4 = 3`) koji
   se nikad ne ispravi kroz ostatak fajla za ovaj config. PicoRV32
   (`CATCH_MISALIGN=1` po defaultu) trapuje neporavnat pristup; bez
   bus-error IRQ-a na ovom minimalnom top-u, jezgro ide u trajan
   `cpu_state_trap` — tih, potpun zastoj. Potvrđeno da je grešku nemoguće
   popraviti unutar ovog targeta (dodiruje `c_engine/upstream/atome.c`,
   van dozvoljenog obima za target PR po CONTRIBUTING.md). Native x86 build
   iste checkpoint datoteke radi bit-egzaktno (toleriše neporavnat pristup
   hardverski) — dokaz da je bug isključivo upstream, ne u ovom kodu. Puni
   nalaz: `c_engine/targets/picorv32-tangnano9k/README.md` ("A third bug"),
   `hardware/tangnano9k/evidence/serial_alignment_bug_log_tangnano9k.txt`.
6. **Usput pronađen i popravljen i DRUGI target-side bug**: RAM na ovoj
   platformi počinje na adresi `0x00000000`, pa je `g_tokens` slučajno
   linkovan baš tamo — `atome.c`-ova standardna `if (!tokens) return -1;`
   NULL provjera je pogrešno tretirala validan pokazivač kao NULL, pa je
   `atome_predict_next` tiho vraćao -1 na svaki poziv (bez ikakve stvarne
   računice) sve dok ovo nije popravljeno. Popravka: rezervisana prva
   riječ RAM-a u `linker.ld`. **Ovo znači da je prvobitni "boot" evidence
   log (`FF FF FF FF...`) bio pogrešno protumačen** ("očekivan šum od
   netreniranih težina") — stvarni uzrok je bio ovaj bug, ne slučajni
   argmax. Ispravka je dodana u sam evidence log fajl.

Pun izvještaj sa tabelama: [`c_engine/targets/picorv32-tangnano9k/README.md`](c_engine/targets/picorv32-tangnano9k/README.md).

## Sljedeći korak

Faze 0, 2, 3, 4 i 5 su završene, uključujući direktno mjerenje stack
high-water marka na stvarnom hardveru (margina 1628 B / 9.9% slobodno —
tijesno, ali potvrđeno, ne procijenjeno) i pronalazak/popravku DVA
stvarna target-side bug-a (NULL@0x0 pointer aliasing, `rv32imc` hang).
Pravi (seed=42, ne placeholder) `nano` checkpoint postoji
(`nano_seed42.atome`, `torch` instaliran i korišten), bit-egzaktno
potvrđen protiv Python reference — ali NATIVNO, ne na hardveru, jer je
otkriven TREĆI bug (tačka 5 gore) koji je **upstream**, ne u ovom
targetu, i blokira stvarnu on-hardware parity provjeru dok se ne
popravi tamo.

Status: **implementacija ovog targeta je gotova i tehnički ispravna** —
sve što je pod našom kontrolom (linker.ld, start.s, uart.c, firmware.c,
Makefile, build sistem) je verifikovano na pravom hardveru. Ono što
NEDOSTAJE (pravi, čitljiv parity dokaz na hardveru) nije nešto što ovaj
target može sam popraviti — čeka upstream fix. Ostaje prije Faze 6 (PR):

- Prijaviti upstream bug (ATOME01 format misalignment) kao GitHub issue
  na `TilelliLab/atome-lm` — draft teksta pripremljen, čeka tvoju potvrdu
  prije objave (isti workflow kao i za ostale contributione).
- Faza 6 (PR) za sam target može ići i BEZ čekanja na upstream fix — može
  se jasno navesti u PR opisu da je port kompletan i hardverski
  verifikovan do granice upstream bug-a, sa punom dokumentacijom i
  reproducibilnim putem za parity test čim se upstream popravi.

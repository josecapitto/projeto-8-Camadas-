# Projeto 8

Este diretório contém as duas partes do projeto:

- Parte 1 - modulação AM: execute `main.py` e consulte este documento;
- Parte 2 - chat com BPSK: execute `parte2_psk.py` e consulte `README_PARTE2.md`.

---

# Parte 1 - Modulação AM

Esta aplicação simula, de maneira simples e didática, três estações de rádio AM. Ela grava três áudios, coloca cada um em sua faixa de transmissão, soma os sinais para representar o meio físico, separa os canais no receptor e recupera os três áudios.

O código evita técnicas avançadas de mercado. A modulação é uma multiplicação ponto a ponto, os filtros são construídos com uma equação FIR simples e cada etapa está separada e comentada no arquivo `main.py`.

## 1. Preparação

É necessário ter o Python 3.11 ou mais recente instalado.

No PowerShell, dentro desta pasta, execute:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Se o comando `python` não for reconhecido, instale o Python pelo site oficial e marque a opção de adicioná-lo ao PATH.

## 2. Execução

Inicie o programa com:

```powershell
.\.venv\Scripts\python.exe main.py
```

Use as opções do menu nesta ordem:

1. Grave os três áudios originais. Fale algo diferente em cada estação.
2. Execute os três originais para a apresentação.
3. Faça a modulação, a soma, a recepção e a demodulação. Os três conjuntos de gráficos FFT serão gerados e abertos.
4. Reabra os gráficos sem precisar repetir o processamento, se necessário.
5. Execute os três áudios demodulados.

Use fones de ouvido durante os testes. Os sinais modulados ficam em frequências altas e podem ser desagradáveis quando reproduzidos.

A parte AM grava, processa e salva os novos resultados em **44.100 Hz**. Os
WAVs antigos de 48.000 Hz são reamostrados ao serem lidos: a conversão mantém
a duração e a frequência da voz e remove componentes acima do novo limite
de Nyquist. Os arquivos originais permanecem preservados. Não basta trocar
apenas a taxa escrita no cabeçalho de um WAV.

O arquivo de dados dos gráficos registra a taxa de amostragem. Se a opção `4`
encontrar um processamento antigo sem essa informação, ela refaz os cálculos
usando 44.100 Hz antes de mostrar os gráficos.

## 3. Ideia do projeto

As faixas e suas portadoras são:

| Estação | Faixa permitida | Portadora |
|---|---:|---:|
| 1 | 9 a 12 kHz | 10,5 kHz |
| 2 | 12 a 15 kHz | 13,5 kHz |
| 3 | 15 a 18 kHz | 16,5 kHz |

Cada faixa tem 3 kHz de largura. Como a modulação AM cria uma cópia do espectro em cada lado da portadora, o áudio poderia ocupar no máximo 1,5 kHz. O programa limita o áudio a 1,3 kHz, deixando uma margem de segurança de 200 Hz em cada borda.

### Emissor

Para cada estação, o áudio filtrado `m(t)` é multiplicado pela portadora:

```text
s(t) = m(t) * sen(2*pi*fc*t)
```

As três estações moduladas são somadas:

```text
meio_fisico = (estacao1 + estacao2 + estacao3) / 3
```

A divisão por 3 serve somente para impedir que o arquivo de áudio fique saturado.

### Receptor

Um filtro passa-faixa seleciona uma estação. O sinal separado é multiplicado novamente por uma portadora de mesma frequência e fase:

```text
produto = 2 * sinal_extraido * sen(2*pi*fc*t)
```

Essa multiplicação devolve uma parcela para as frequências originais e cria outra em alta frequência. Um filtro passa-baixa remove a parcela alta, deixando o áudio recuperado.

## 4. Arquivos produzidos

- `audios/originais/`: as três gravações feitas pelo microfone;
- `audios/resultados/`: sinais modulados, soma, canais extraídos e áudios demodulados;
- `graficos/01_fft_modulados.png`: FFT dos três canais transmitidos;
- `graficos/02_fft_meio_fisico.png`: FFT da soma das três estações;
- `graficos/03_fft_extraidos.png`: FFT dos canais separados no receptor.

## 5. Roteiro curto para explicar ao professor

1. A taxa de amostragem é 44.100 Hz, como solicitado.
2. O áudio é limitado a 1.300 Hz para caber dentro de uma faixa AM de 3 kHz.
3. A modulação desloca o espectro do áudio para perto da portadora.
4. As três estações podem ser somadas porque ocupam faixas diferentes.
5. O receptor escolhe uma faixa com um filtro passa-faixa.
6. A multiplicação pela mesma portadora e o filtro passa-baixa recuperam o áudio.
7. O programa calcula a porcentagem de energia dentro de cada faixa; o resultado deve aparecer como `OK`.

## 6. Simplificações assumidas

Este é um simulador educacional. O transmissor e o receptor usam o mesmo relógio, então a portadora local tem frequência e fase perfeitas. Também não foram adicionados ruído, interferência, atraso de propagação ou circuitos de controle automático de ganho. Essas simplificações permitem enxergar diretamente a matemática solicitada no enunciado.

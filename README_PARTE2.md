# Projeto 8 - Parte 2 - Chat com BPSK

Esta aplicação transmite texto entre dois computadores usando som. O emissor transforma os caracteres em bits, modula uma portadora de áudio com BPSK e toca o resultado no alto-falante. O receptor grava pelo microfone, demodula o sinal e escreve a mensagem no terminal.

O mesmo arquivo `parte2_psk.py` é usado nos dois computadores.

## 1. Instalação

Em cada computador, abra o PowerShell na pasta do projeto e execute:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. Teste automático sem microfone

Antes de usar dois computadores, execute:

```powershell
.\.venv\Scripts\python.exe teste_parte2.py
```

O resultado esperado termina com:

```text
[OK] Conversao de texto, bytes e bits
[OK] Modulacao e demodulacao com atraso, atenuacao e ruido
[OK] Taxas e portadoras alternativas
Todos os testes da Parte 2 passaram.
```

## 3. Teste local pelo menu

Execute:

```powershell
.\.venv\Scripts\python.exe parte2_psk.py
```

1. Escolha `1`, digite uma frase e aguarde o áudio terminar.
2. Escolha `3` para decodificar diretamente o último arquivo emitido.
3. A frase recuperada deve ser idêntica à digitada.

Esse teste comprova a lógica, mas ainda não testa alto-falante e microfone.

## 4. Teste entre dois computadores

Copie o projeto para os dois computadores. Ambos devem usar a configuração padrão de `100 bits/s` e portadora de `4000 Hz`.

### Computador receptor

1. Execute `parte2_psk.py`.
2. Escolha `2 - RECEPTOR`.
3. Use inicialmente 12 segundos de gravação.
4. Pressione Enter para começar a gravar.

### Computador emissor

1. Deixe o alto-falante próximo ao microfone do receptor, sem encostar.
2. Execute `parte2_psk.py`.
3. Escolha `1 - EMISSOR`.
4. Digite uma frase curta e pressione Enter enquanto o receptor estiver gravando.

Quando a gravação terminar, o receptor deve mostrar `MENSAGEM RECEBIDA` e a frase original.

Comece com os computadores separados por aproximadamente 30 a 60 centímetros, volume entre 50% e 70% e ambiente silencioso. Volume máximo pode provocar distorção.

## 5. Gráficos pedidos

Depois da transmissão, os arquivos ficam em:

- `parte2/graficos/01_fft_emitido.png`;
- `parte2/graficos/02_fft_recebido.png`.

No menu, a opção `7` mostra os dois gráficos. A região verde representa aproximadamente o lóbulo principal do BPSK. Em 100 bits/s, ele vai de `fc - 100 Hz` até `fc + 100 Hz`, resultando em aproximadamente 200 Hz.

## 6. Experimentos pedidos no enunciado

### Alterar a taxa

Escolha a opção `4`. O gráfico compara 50, 100 e 200 bits/s.

Resultado esperado: quanto maior a taxa de bits, mais rapidamente a fase muda e mais largo fica o espectro. Aproximadamente:

| Taxa | Largura do lóbulo principal |
|---:|---:|
| 50 bits/s | 100 Hz |
| 100 bits/s | 200 Hz |
| 200 bits/s | 400 Hz |

### Alterar a portadora

Escolha a opção `5`. O gráfico compara 2,5, 4 e 5,5 kHz.

Resultado esperado: mudar a portadora desloca o espectro para a esquerda ou direita, mas não altera significativamente sua largura quando a taxa permanece igual.

## 7. Como explicar o código

### Texto para bits

O texto é convertido em bytes UTF-8 e cada byte vira oito bits. O quadro transmitido contém:

```text
preambulo | marcador | tamanho | texto | checksum
```

- o preâmbulo ajuda a encontrar o começo e a fase;
- o marcador confirma a sincronização;
- o tamanho informa quantos bytes devem ser lidos;
- o checksum detecta bits incorretos.

### BPSK

Cada bit controla a fase da portadora:

```text
bit 1 -> cosseno normal, fase de 0 graus
bit 0 -> cosseno invertido, fase de 180 graus
```

Matematicamente, o programa multiplica a portadora por `+1` ou `-1` durante cada bit.

### Demodulação

O receptor multiplica o áudio por uma portadora complexa local e soma as amostras de cada intervalo de bit. O preâmbulo conhecido permite estimar a fase introduzida pelo atraso entre alto-falante e microfone. Depois da correção:

```text
resultado positivo -> bit 1
resultado negativo -> bit 0
```

## 8. Diagnóstico de problemas

- `Nenhum sinal PSK detectado`: aumente moderadamente o volume ou aproxime os computadores.
- `Sincronização fraca`: reduza ruídos e confirme que os dois lados usam a mesma portadora e taxa.
- `Checksum incorreto`: houve erro em um ou mais bits; diminua a distância ou o volume se estiver distorcendo.
- `Gravação terminou antes do final`: aumente o tempo de gravação.
- mensagem errada em caracteres acentuados: confirme que o checksum passou; UTF-8 já é suportado.

## 9. Roteiro para apresentação

1. Mostre a configuração padrão: 100 bits/s e 4 kHz.
2. No receptor, inicie uma gravação de 12 segundos.
3. No emissor, digite uma frase e pressione Enter.
4. Mostre a frase aparecendo no receptor.
5. Abra as FFTs emitida e recebida com a opção `7`.
6. Explique a banda aproximada de 200 Hz.
7. Use a opção `4` para mostrar que aumentar a taxa alarga a FFT.
8. Use a opção `5` para mostrar que mudar a portadora desloca a FFT.

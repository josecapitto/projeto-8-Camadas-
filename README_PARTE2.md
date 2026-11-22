# Projeto 8 - Parte 2 - Chat com BPSK

Esta aplicação transmite texto entre dois computadores usando som. O emissor transforma os caracteres em bits, modula uma portadora de áudio com BPSK e toca o resultado no alto-falante. O receptor grava pelo microfone, demodula o sinal e escreve a mensagem no terminal.

O mesmo arquivo `parte2_psk.py` é usado nos dois computadores.

A configuração padrão é **100 bits úteis/s dos caracteres**, portadora de
**4.000 Hz** e amostragem de **48.000 Hz**. Cada bit dos dados continua sendo
repetido três vezes para corrigir erros: a taxa física BPSK é **300 bits/s**,
ou 300 símbolos/s, com 160 amostras por símbolo. O menu sempre informa as duas
taxas. A amostragem de 44.100 Hz é usada na parte 1; esta parte mantém 48.000 Hz.

O novo quadro tem preâmbulo de 192 bits e marcador de 96 bits. O treinamento
continua durando 0,96 segundo em sua configuração padrão, apesar do aumento
da taxa física. O receptor reconhece também os dois formatos anteriores,
incluindo a gravação da sala, sem alterar esses WAVs.

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

Os testes incluem uma gravação real que antes falhava no marcador, além de
ruído, ecos, transiente forte, desvio de frequência, diferenças entre relógios
de áudio, formato antigo e rejeição de mensagens corrompidas. O resultado
esperado termina com:

```text
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

Para testar uma gravação recebida anteriormente, use a opção `8` do menu ou:

```powershell
.\.venv\Scripts\python.exe parte2_psk.py --decodificar parte2/resultados/audio_recebido.wav
```

Esse comando não grava pelo microfone nem altera os áudios ou gráficos salvos.
Para outro arquivo ou configuração, informe o caminho e, se necessário,
`--taxa 100 --portadora 4000`. `--taxa` indica bits úteis/s para novos quadros.
Na tentativa de compatibilidade com versões anteriores, o receptor também
testa esse mesmo número como taxa física antiga e informa as taxas realmente
detectadas: a gravação repetida da sala continua tendo 100 bits físicos/s e
aproximadamente 33,3 bits úteis/s. Ela não é acelerada nem regravada.

## 4. Teste entre dois computadores

Atualize o projeto nos dois computadores. Ambos devem usar a configuração
padrão de `100 bits úteis/s` (300 bits físicos/s) e portadora de `4000 Hz`.
Um receptor antigo não reconhece o novo quadro.

### Computador receptor

1. Execute `parte2_psk.py`.
2. Escolha `2 - RECEPTOR`.
3. Use inicialmente 15 segundos de gravação.
4. Pressione Enter para começar a gravar.

### Computador emissor

1. Deixe o alto-falante próximo ao microfone do receptor, sem encostar.
2. Execute `parte2_psk.py`.
3. Escolha `1 - EMISSOR`.
4. Comece com `ola` e pressione Enter enquanto o receptor estiver gravando.

Quando a gravação terminar, o receptor deve mostrar `MENSAGEM RECEBIDA` e a frase original.

Comece com os computadores separados por aproximadamente 10 a 30 centímetros, volume entre 40% e 60% e ambiente silencioso. Volume máximo pode provocar distorção.

Desative supressão de ruído, cancelamento de eco e melhorias de voz do microfone
quando essas opções estiverem disponíveis: elas podem atenuar ou deformar um
modem de áudio, mesmo quando a fala é captada normalmente. Se houver mais de um
microfone conectado, confira qual está selecionado como entrada padrão.

O quadro atual dura `(360 + 24 × bytes UTF-8) / (3 × taxa_util)` segundos,
mais 1,3 segundo de silêncio. Em 100 bits úteis/s, isso equivale a
`2,5 + 0,08 × bytes UTF-8` segundos no total: uma mensagem de 50 bytes ocupa
6,5 segundos. Reserve também tempo para iniciar a transmissão.

Os caracteres são enviados a 100 bits úteis/s durante os dados. Preâmbulo,
marcador, cabeçalho, checksum e silêncios acrescentam tempo ao quadro; por isso,
dividir os bits do texto pela duração de toda a gravação dá uma taxa média menor.
Caracteres acentuados podem ocupar mais de um byte UTF-8.

## 5. Gráficos pedidos

Depois da transmissão, os arquivos ficam em:

- `parte2/graficos/01_fft_emitido.png`;
- `parte2/graficos/02_fft_recebido.png`.

No menu, a opção `7` mostra os dois gráficos. A região verde representa o
lóbulo principal dos pulsos BPSK retangulares, calculado pela taxa **física**.
Em 100 bits úteis/s (300 físicos/s), vai de `fc - 300 Hz` até `fc + 300 Hz`,
resultando em aproximadamente **600 Hz**. Em torno de 4 kHz, é a faixa de
3,7 a 4,3 kHz. A repetição concentra parte da energia dos dados em uma região
mais estreita; o treinamento e o marcador também participam da FFT completa.

Cada recepção também é preservada em uma pasta própria:
`parte2/resultados/capturas/AAAAMMDD_HHMMSS_microssegundos/`. Ela contém o
WAV, a FFT e `diagnostico.json`, com taxa, portadora e sucesso ou motivo da
falha. A FFT é atualizada mesmo quando a mensagem não é decodificada.

## 6. Experimentos pedidos no enunciado

### Alterar a taxa

Escolha a opção `4`. O gráfico compara 50, 100 e 200 bits **úteis/s**.

Resultado esperado: quanto maior a taxa de bits, mais rapidamente a fase muda e mais largo fica o espectro. Aproximadamente:

| Taxa útil | Taxa física BPSK | Largura do lóbulo principal |
|---:|---:|---:|
| 50 bits/s | 150 bits/s | 300 Hz |
| 100 bits/s | 300 bits/s | 600 Hz |
| 200 bits/s | 600 bits/s | 1.200 Hz |

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

Os bits de tamanho, texto e checksum são transmitidos três vezes, à taxa
física de três vezes a taxa útil configurada. O receptor
escolhe o valor majoritário de cada grupo, corrigindo um erro em cada trio.
Antes da decisão, ele filtra a região da portadora, procura vários candidatos
na gravação inteira e compensa pequenas diferenças entre as placas de som.
Um candidato só é aceito após validar marcador, tamanho, UTF-8 e checksum.

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

A estimativa de fase limita a influência de picos fortes. Um acompanhamento
de fase durante os dados evita que um pequeno erro de frequência se acumule
até inverter os bits no final de uma mensagem longa.

Se a recepção simples falhar, um equalizador FIR complexo de duas amostras por
bit usa a sequência conhecida para compensar a mistura entre símbolos causada
pelo canal. A primeira metade do preâmbulo é descartada nesse ajuste, pois o
início pode estar afetado por um transiente. Cada bit de treinamento é também
avaliado sem participar do próprio ajuste (validação leave-one-out), e a
repetição dos dados precisa apresentar pelo menos 90% de concordância. A
equalização não dispensa o marcador nem o checksum.

O alcance do equalizador é ajustado em função da taxa física para cobrir
aproximadamente o mesmo intervalo de ecos em segundos. Na configuração padrão,
o filtro maior tem 37 coeficientes; na gravação antiga de 100 bits físicos/s,
continua usando 13. A busca é dividida em blocos para limitar o uso de memória.

## 8. Diagnóstico de problemas

- `Nenhum sinal PSK detectado`: aumente moderadamente o volume ou aproxime os computadores.
- `Sincronização fraca ou marcador não encontrado`: nenhum candidato passou na validação; confirme o microfone, a portadora e a taxa, e desative os filtros de voz da entrada de áudio. O receptor já tenta compensar fase e distorção entre símbolos.
- `Checksum incorreto`: houve erro em um ou mais bits; diminua a distância ou o volume se estiver distorcendo.
- `Gravação terminou antes do final`: aumente o tempo de gravação.
- mensagem errada em caracteres acentuados: confirme que o checksum passou; UTF-8 já é suportado.

Na investigação das gravações de 19/11, o WAV emitido salvo usava o formato
antigo, enquanto o WAV recebido usava o formato repetido anterior. O receptor corrigido recupera
ambos. A gravação real recebida apresentava um transiente forte e distorção
entre símbolos; o receptor anterior falhava no marcador, e a equalização
recupera os 312 bits do quadro com checksum válido. Não é possível atribuir
a distorção a um ajuste específico do microfone apenas pelo WAV.

O WAV recebido de cinco segundos preservado no commit `2125fdb` também foi
analisado, mas não produziu um quadro validável. A recuperação confirmada é
a do WAV atual de seis segundos e das gravações emitidas; não há evidência
suficiente para atribuir a falha daquele WAV mais antigo à mesma causa.

O gráfico recebido antigo também era de outra tentativa: antes da correção,
ele só era salvo depois de uma decodificação bem-sucedida. Uma FFT mostra a
distribuição em frequência, mas não comprova o alinhamento dos bits nem a
integridade da mensagem.

## 9. Roteiro para apresentação

1. Mostre a configuração padrão: 100 bits úteis/s, 300 físicos/s e 4 kHz.
2. No receptor, inicie uma gravação de 15 segundos.
3. No emissor, digite uma frase e pressione Enter.
4. Mostre a frase aparecendo no receptor.
5. Abra as FFTs emitida e recebida com a opção `7`.
6. Explique a banda aproximada de 600 Hz e a diferença entre taxa útil e física.
7. Use a opção `4` para mostrar que aumentar a taxa alarga a FFT.
8. Use a opção `5` para mostrar que mudar a portadora desloca a FFT.

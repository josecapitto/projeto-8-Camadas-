# Gravação de regressão BPSK

`recepcao_sala.wav` é uma cópia da gravação real de seis segundos disponível
em `parte2/resultados/audio_recebido.wav` durante a investigação de 22/11/2026.
Seu SHA-256 é `CF84D91CB0683C5E63B22B76A2D8CA50AE9779E23A5C770B245FC4D9EB8B9E00`.

O receptor anterior escolhia o início na amostra 74781, apresentava métrica
0,846 e falhava no marcador. O início tem um transiente muito mais forte que
o restante do quadro; os símbolos recebidos também apresentam interferência
entre si. O receptor corrigido recupera a mensagem do quadro anterior de 312 bits com
equalização, repetição por maioria, UTF-8 e checksum válidos.

Esse WAV permanece em 100 bits físicos/s (33,3 úteis/s). O receptor atual
detecta o formato `anterior` automaticamente. As novas transmissões usam
100 bits úteis/s, 300 físicos/s e um treinamento maior.

Este arquivo fica separado das capturas de uso para que novas gravações não
substituam o caso de regressão. Execute `teste_parte2.py` para reproduzir.

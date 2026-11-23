# Jogo da Forca P2P

Projeto para a disciplina de Redes de Computadores. Implementação de um cliente P2P (Peer-to-Peer) do Jogo da Forca. O sistema opera de forma descentralizada, utilizando um servidor Rendezvous apenas para registro e descoberta inicial de peers, enquanto toda a comunicação de lobby e o andamento das partidas ocorrem diretamente entre os nós por meio de conexões TCP persistentes.

## Resumo e Objetivos

O trabalho consiste na implementação de um cliente P2P de Jogo da Forca que:

- Registra-se em um servidor Rendezvous e descobre outros peers de forma recorrente e automática;
- Mantém conexões TCP persistentes com os peers descobertos (malha de descoberta);
- Permite que qualquer peer crie uma partida e atue como host;
- Permite que outros peers descubram e entrem em partidas abertas;
- Conduz a partida por turnos, com o host mantendo o estado autoritativo;
- Mantém sessões vivas com PING/PONG e as encerra com BYE/BYE_OK;
- Tolera a saída inesperada de jogadores e a queda do host.

Não há servidor de jogo central: o Rendezvous apenas registra e lista peers; toda a lógica do jogo roda nos próprios peers.

## Grupo 9 — Integrantes

- Arthur Correia Marques — 241022316
- Gustavo Pires dos Santos — 251004349
- Helton Rodrigues da Silva Junior — 251021789

## Executar

### Linux

No terminal, a partir da pasta raiz do projeto:

```bash
python3 --version
cd caminho/do/projeto
python3 src/main.py
```
caso não tenha o python instalado:
```bash
sudo apt update && sudo apt install python3
```

### Windows

No terminal (PowerShell ou CMD), a partir da pasta raiz do projeto:

```bash
python --version
cd caminho/do/projeto
python src\main.py
```

Ou, usando o launcher do Python:

```bash
py -3 --version
py -3 src\main.py
```

> No Windows o comando é `python` (ou `py -3`);

O programa carrega `config.json` automaticamente. Para encerrar, use `/quit` ou `Ctrl+C`.

## Configuração

Edite `config.json` antes de iniciar o programa. Os campos mais importantes são:

| Campo | Descrição |
| --- | --- |
| `name` | Nome deste peer. |
| `namespace` | Namespace usado para agrupar e descobrir peers. |
| `listen_port` | Porta TCP em que este peer aceita conexões. |
| `rdv_host` e `rdv_port` | Endereço e porta do servidor Rendezvous. |
| `register_ttl` | Tempo de validade do registro, em segundos. |
| `discover_interval` | Intervalo entre ciclos de descoberta, em segundos. |
| `ping_interval` e `ping_miss_limit` | Intervalo e limite de falhas do keep-alive. |
| `max_reconnect_attempts`, `base_backoff` e `max_backoff` | Parâmetros de tentativas e espera para reconexão. |
| `lives`, `max_players` e `turn_timeout` | Regras padrão das partidas. |
| `words_file` | Arquivo usado para sortear palavras em `/create --random`. |
| `log_file` | Arquivo para gravar logs.

## Logs

Para habilitar e salvar logs para diagnóstico:

1. No campo `log_file` do `config.json`, informe o caminho do arquivo de log (ex.: `"logs/app.log"`). Se for `null`, apenas os logs exibidos na tela são gerados.
2. A tela exibe logs de nível `INFO` por padrão; o arquivo de log salva níveis `DEBUG` e superiores.
3. É possível alterar o nível na tela a qualquer momento com o comando `/log <DEBUG|INFO|WARNING|ERROR>`.

Exemplo de saída no arquivo de log:

```text
2026-11-23 10:00:00 INFO [RDV] Peer iniciado como helton@CIC (ttl=7200)
```

## Comandos da CLI

Digite `/help` dentro do programa para ver a ajuda. Os comandos disponíveis são:

| Comando | Ação |
| --- | --- |
| `/peers [* \| #namespace]` | Descobre e lista peers; sem argumento, usa o namespace local. |
| `/conn` | Lista conexões ativas, direção, estado e RTT. |
| `/rtt` | Mostra o RTT médio disponível por peer. |
| `/reconnect` | Força uma nova reconciliação com o Rendezvous. |
| `/games` | Consulta os vizinhos sobre partidas disponíveis. |
| `/create <palavra> [max_players]` | Cria uma partida hospedada por você. |
| `/create --random [max_players]` | Cria uma partida com palavra sorteada do arquivo configurado. |
| `/start` | Inicia a partida hospedada; é necessário ao menos um jogador. |
| `/cancel` | Cancela a partida hospedada. |
| `/join <host_peer_id>` | Entra em uma partida, por exemplo: `/join alice@CIC`. |
| `/leave` | Sai da partida atual. |
| `/guess <letra>` | Envia um palpite de letra. |
| `/word <palavra>` | Envia um palpite da palavra inteira. |
| `/status` | Mostra o estado local da partida. |
| `/log <DEBUG\|INFO\|WARNING\|ERROR>` | Altera o nível de log. |
| `/help` | Lista os comandos disponíveis. |
| `/quit` | Encerra o programa e a participação na partida, se houver. |

## Arquitetura de Módulos

| Módulo | Responsabilidade |
| --- | --- |
| `main.py` | Argumentos, carga do `config.json`, logging, inicialização |
| `p2p_client.py` | Orquestração: registro, tarefas periódicas, encerramento |
| `rendezvous_connection.py` | `REGISTER` / `DISCOVER` / `UNREGISTER` |
| `peer_connection.py` | Servidor e cliente TCP, framing JSON-por-linha, `HELLO`, desempate |
| `peer_table.py` | Estados, RTT, backoff, reconciliação |
| `keep_alive.py` | `PING` / `PONG` |
| `message_router.py` | Validação e despacho por tipo |
| `game_host.py` | Máquina de estados do host, turnos, timeout |
| `game_player.py` | Máquina do jogador, verificação de `seq` e `word_hash` |
| `hangman.py` | Lógica pura do jogo |
| `cli.py` | Interface de comandos |

## Estrutura do projeto

```text
src/
├── main.py        # Inicialização do peer
├── words.txt      # Lista de palavras para /create --random
├── conections/   # Conexões TCP, Rendezvous, descoberta e keep-alive
├── game/         # Regras e estado das partidas
└── interface/    # CLI e configuração de logs
config.json       # Configuração local do peer
```

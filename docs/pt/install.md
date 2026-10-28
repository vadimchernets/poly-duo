# Instalar o Duo — 2 minutos, sem conhecimento técnico

O C1M Duo é um "atalho" para iPhone: você faz uma pergunta e ela é trabalhada por duas IAs ao mesmo tempo — ChatGPT e Claude — em um de doze modos. A resposta chega na sua tela e na sua área de transferência.

## Antes de instalar (uma única vez)

1. **Um iPhone com iOS 18 ou posterior.** Esse é o mínimo oficial da ação "Ask Claude" sobre a qual o Duo é construído (a própria documentação da Anthropic diz "iOS 18 and later"). Além disso, no iOS 26 a Apple lista como compatíveis o iPhone 11 e posteriores e o SE de 2ª geração e posteriores. O Duo em si não exige o Apple Intelligence — só iOS 18+. Espera-se que o iPad funcione no iPadOS 18+/26, mas isso não foi testado na prática. O complemento **Poly Compress** precisa especificamente de hardware com Apple Intelligence: um chip A17 Pro / da série M ou mais novo (iPhone 15 Pro/Pro Max, qualquer 16/16e e posteriores, iPad com M1+ ou o mini com A17 Pro).
2. **Os apps ChatGPT e Claude**, instalados pela App Store e com a sessão iniciada nos dois. As contas gratuitas bastam: o Claude gratuito usa o Sonnet 5.5, o mesmo modelo do plano pago, e a ação Ask Claude usa o modelo escolhido no app do Claude.

## Instalação (um toque)

### O mais fácil — o link do iCloud (um toque)

No iPhone, toque no link → o app Atalhos abre → **Adicionar**. Na primeira execução o atalho pede permissão 4–6 vezes — toque em **Sempre Permitir** todas as vezes.

- **Duo:** https://www.icloud.com/shortcuts/eb3370375aed49ee99b289cf125ac1a5
- **Trio, iPhone 15 Pro ou mais novo — sem chave** (a terceira voz é a Apple Intelligence; veja abaixo): https://www.icloud.com/shortcuts/4000dcb2b9d64dcfaa44062c92e51b69
- **Trio, iPhone mais antigo — chave gratuita** (a terceira voz, veja abaixo): https://www.icloud.com/shortcuts/29cace07d31f4033aa0cf26a2d1f9bb1

### Alternativa — o arquivo

Os arquivos assinados `Duo.shortcut` e `Trio.shortcut` estão em [polyhelper.ai/duo/pt/](https://polyhelper.ai/pt/duo/) e na [versão do GitHub](https://github.com/vadimchernets/poly-duo/tree/main/releases). Ou então:

1. Leve o arquivo **`dist/pt/Duo.shortcut`** até o telefone do jeito que preferir: AirDrop, WhatsApp/Telegram, e-mail, um pen drive — tanto faz.
2. Toque no arquivo. O app Atalhos abre com um cartão "Duo" — toque em **Adicionar**. Pronto, o Duo está instalado.
   - Se o arquivo chegou por um mensageiro, toque nele lá primeiro, escolha Compartilhar/"Abrir em…" e então selecione Atalhos.
3. **Primeira execução:** o atalho pede permissões — "Permitir as ações do ChatGPT?" → Permitir; "…enviar texto ao Claude?" → **Sempre Permitir**; "…copiar para a área de transferência?" → **Sempre Permitir**. Isso acontece uma única vez.

## Ícone na Tela de Início (30 segundos, opcional)

1. Abra o Atalhos → mantenha o dedo no bloco do Duo → se nenhum menu aparecer, toque em "···" no bloco → toque no nome **Duo ⌄** lá em cima → **"Adicionar à Tela de Início"**.
2. Quer o ícone da marca? Toque na miniatura → aba "Imagem" → "Escolher Foto/Arquivo" → selecione `assets/poly.jpg` (mande esse arquivo para o telefone junto com o atalho).
3. Toque em **Adicionar**. O ícone do Duo aparece na sua Tela de Início — um toque para abrir. Por voz: "E aí Siri, Duo".

## Como usar

Toque no ícone → "O que você quer perguntar ao Duo?" → digite sua pergunta → "Concluído" → escolha um modo. O menu tem dois níveis: os seis modos mais comuns em cima e todo o resto guardado em **📂 Mais…** (nada foi removido — um modo raro custa apenas um toque a mais). Em Mais… fica também **ℹ️ O que é o Duo**, uma explicação gratuita de cada modo, direto no aparelho. Perdido na hora de escolher o modo? Abra essa opção — ela não gasta uma única mensagem.

**Menu principal (modos comuns):**

| Modo | O que acontece | Custo |
|---|---|---|
| **⚖️ Crítica · 3✉** | O ChatGPT e o Claude respondem cada um por conta própria, sem se verem; o Claude compara as duas respostas e entrega a final, aberta por três blocos: bateu de forma independente / não bateu / o que conferir você mesmo. Seu modo do dia a dia. | 3 mensagens |
| **🤝 Debate até o acordo · 3–8✉** | Para decisões de vida sem resposta certa («o que escolher», «se devo aceitar»). O ChatGPT escolhe um lado, o Claude contesta, o ChatGPT responde — até 3 rodadas, até que um ceda de verdade. No fim: onde concordaram, o que segue em disputa, o que você decide. | 3–8 mensagens |
| **🩺 Consultor · 1✉** | O Claude analisa o SEU texto pronto sem reescrevê-lo: um veredicto em uma linha, a objeção mais forte primeiro, o que verificar. O modo mais barato. | 1 mensagem |
| **👀 Lado a lado · 2✉** | Os dois respondem de forma independente; as respostas ficam uma ao lado da outra. | 2 mensagens |
| **🔀 Síntese · 3✉** | Os dois respondem às cegas e depois as respostas são fundidas em um resultado do tipo "âncora + delta". Você será perguntado sobre quem ancora: Claude (fatos/estrutura) ou ChatGPT (tom/criatividade). Para tudo o que importa. | 3 mensagens |
| **🧭 Auto · +1✉** | Não sabe qual modo usar? O ChatGPT escolhe um por você (+1 mensagem) e então o Duo recomeça com a mesma pergunta, para você selecionar o modo recomendado. | 1 mensagem + o modo |

**📂 Mais… (modos ocasionais + ajuda gratuita):**

| Modo | O que acontece | Custo |
|---|---|---|
| **⚔️ Decisão · 3✉** | Um olhar rápido (ChatGPT) encontra um olhar cauteloso (Claude), e então um árbitro apresenta os primeiros passos e os riscos. Para decisões. | 3 mensagens |
| **🗺 Mapa de divergências · 3✉** | Os dois respondem às cegas e o resultado vira um mapa: onde concordam, onde divergem, pontos cegos, o que verificar. Sem conclusão forçada — quem decide é você. | 3 mensagens |
| **🥊 Debate · 4✉** | Um rascunho, um oponente caçando pontos fracos, uma revisão e então o veredicto de um juiz. Para os problemas mais difíceis. | 4 mensagens |
| **❓ Esclarecer · 2✉** | O ChatGPT pergunta primeiro o que está faltando → você responde em uma janela que aparece → o Claude dá uma resposta precisa. Para perguntas vagas. É o único modo em que se espera que você toque na tela no meio da execução — mas só no diálogo dele, em mais nada. | 2 mensagens |
| **➕ Delta · 2✉** | O Claude escreve a resposta-âncora → o ChatGPT devolve APENAS uma lista de melhorias em tópicos, sem reescrever tudo. Uma alternativa mais barata à Síntese quando você está cuidando do orçamento de mensagens. | 2 mensagens |
| **🎨 Imagem · 2–3✉** | Descreva o que deve ser desenhado → os dois artistas de IA fazem o esboço às cegas (SVG vetorial, cada um em uma sessão limpa — sem espiar o outro) → abre-se uma página com os dois esboços lado a lado, ◆ CLAUDE e ◆ CHATGPT — escolha um (você será perguntado: só os esboços · 2✉ ou + o veredicto de um juiz comparador · 3✉ — o juiz compara o código dos esboços; as imagens renderizadas você já vê por conta própria). A imagem é salva (Arquivos → iCloud Drive → Atalhos → `Duo-image.html`) e o código SVG vai para a área de transferência: cole em qualquer conversor ou site para obter um arquivo de imagem em qualquer tamanho. | 2–3 mensagens |
| **ℹ️ O que é o Duo** | Uma explicação na tela sobre o que é o Duo e qual modo usar em cada situação — sem nenhuma chamada de IA. Dali, "🔁 Outro modo" leva você de volta à escolha de modo com a mesma pergunta. | 0 mensagens |

**Um atalho para dentro do próprio menu** (opcional): deixe por perto o complemento **Poly Quiet** — é uma execução de Crítica pronta em um toque, sem escolha de modo nenhuma (o resultado vai direto para a área de transferência e para o diário, sem telas) — ou o **Poly Voice**, a mesma coisa por voz, com a resposta lida em voz alta. O ícone de qualquer um dos dois pode ir para a Tela de Início como o do Duo, dando a você um "botão rápido" ao lado do menu completo.

O preço aparece dentro do próprio menu (o ícone ✉). Notificações de progresso chegam durante a execução — "[etapa 2/4]…". O diário registra tanto o modo quanto as respostas intermediárias brutas, então, se o resultado final for cortado, os rascunhos não se perdem. A resposta final abre em tela cheia com um botão de compartilhamento (Visualização Rápida).

**Dois níveis.** O nível 1 é o núcleo: o dueto Duo totalmente automático mais os complementos automáticos listados abaixo — instale sem hesitar, é aí que está a inovação central. O nível 2 é uma extensão PRO para usuários avançados: o **🎼 Poly Multi** (um coro manual de 10 IAs dos EUA e da China, com uma síntese Oriente–Ocidente) vem separado e não é necessário para a experiência principal — pegue esse depois que você estiver à vontade com o básico.

**Complementos automáticos do Duo** (só a partir do código-fonte): **Poly Voice** — toque, dite, o fluxo da Crítica roda e a resposta é lida em voz alta (bom para caminhar ou cozinhar); **Poly Photo** — compartilhe uma foto ou um PDF e o OCR do próprio aparelho lê o texto (grátis, sem rede) e o entrega direto ao Duo; **Poly Quiet** — o mesmo fluxo da Crítica, mas sem notificações e sem tela final: o resultado vai só para a área de transferência e para o diário (para execuções rápidas em segundo plano); **Poly Compress** (só em aparelhos com Apple Intelligence: iPhone 15 Pro e posteriores, toda a linha 16/16e/17) — selecione um paredão de texto → Compartilhar → Compress: o modelo gratuito e local da Apple encolhe o texto e abre o Duo automaticamente (proteção contra estouros de tempo em textos longos). Os complementos são para quem compila a partir do código-fonte (`tools/build.sh`); ainda não estão nos links do iCloud. Eles chamam o atalho principal pelo nome "Poly", então renomeie o seu para "Poly" ou edite a ação "Executar Atalho" em cada complemento.

Logo depois de você escolher o modo, chega uma **notificação de status** ("o que está acontecendo e quanto esperar"). Depois é mais ou menos 1–2 minutos até a resposta aparecer na tela e na área de transferência. Formulações prontas para mais de 20 tarefas comuns estão em `recipes.md`. A resposta final sempre começa com o essencial em uma linha e termina com "Confiança: alta/média/baixa". **Enquanto o atalho está rodando, deixe o telefone quieto** — tocar na tela cancela a execução (se parecer que ele morreu em silêncio, é só rodar de novo). A exceção é o **❓ Esclarecer**: por desenho, ele abre uma segunda janela e pede que você responda a perguntas de acompanhamento (ou toque em "pular") — isso não é um defeito, faz parte do fluxo. Responda e o atalho continua sozinho.

## Superpoderes

- **De qualquer app:** selecione o texto → Compartilhar → Duo — sua caixa de pergunta já vem com o texto dentro; acrescente "traduzir/conferir/explicar" e execute.
- **Diário:** cada execução se acrescenta ao `Duo-journal.md` (Arquivos → iCloud Drive → Atalhos). Todo o seu histórico de perguntas e veredictos fica em um lugar só; na primeira execução, libere o acesso a arquivos com **Sempre Permitir**.
- **Abrir sem as mãos:** Ajustes → Botão de Ação → "Executar Atalho" → Duo. Ou um toque duplo nas costas do telefone: Ajustes → Acessibilidade → Toque → Tocar Atrás → Duo. Por voz: "E aí Siri, Duo".
- **Mais portas de entrada:** um widget na Tela de Início ou na Tela Bloqueada (mantenha o dedo na Tela de Início → + → Atalhos → Duo); a Central de Controle (Ajustes → Central de Controle → adicione "Atalhos"); uma etiqueta NFC na sua mesa ou no carro (Atalhos → Automação → NFC → executar o Duo).
- Para iniciar o Duo sem abrir nada (Siri, toque nas costas, tela de bloqueio, Botão de Ação), veja [launch.md](launch.md).
- **Fotos dentro do dueto:** o caminho principal é o complemento **Poly Photo** (compartilhe uma foto/PDF → OCR → ele abre o Duo para você). Para uma leitura *visual* de uma imagem (e não do texto que está nela), use o widget de câmera do Claude → análise → Copiar → compartilhe o texto com o Duo.
- **Conferir a sua própria escrita:** selecione seu rascunho em qualquer lugar → Compartilhar → Duo → modo **🩺 Consultor** — ele analisa sem reescrever (e nunca vira coautor).
- **No iPhone 15 Pro e posteriores:** o Atalhos tem uma ação "Usar Modelo" (Apple Intelligence, grátis, sem internet) que pode estender o Duo — por exemplo, escolhendo o modo automaticamente. No iPhone 14 e anteriores a ação não existe; o Duo funciona bem sem ela.
- **Começar a ouvir na hora (opcional):** no editor do atalho, expanda a primeira ação "Perguntar" e ative o botão de ditado imediato — assim, tocar no ícone já começa a escutar a sua pergunta. Vem desativado, porque isso é mais conveniente tanto para texto digitado quanto para o menu de compartilhamento.

## Trio — a terceira voz (chave gratuita)

`Trio.shortcut` acrescenta uma terceira IA à dupla: ela lê a pergunta, a resposta do ChatGPT e a
resposta final do Claude, e aponta só o que os dois deixaram passar.

**Sem chave (iPhone 15 Pro ou posterior, iOS 26+):** a terceira voz é a própria Apple Intelligence, sem chave nem cadastro. Não sabe qual é o seu iPhone? Ajustes → Geral → Sobre → Nome do Modelo. Instale o Trio sem chave: [English](https://www.icloud.com/shortcuts/2a24e0157e4a445bae92ed1410907b9f) · [Español](https://www.icloud.com/shortcuts/281f56b82f7444438220fdffcbb46f22) · [Português](https://www.icloud.com/shortcuts/4000dcb2b9d64dcfaa44062c92e51b69).

**iPhone mais antigo, ou prefere uma chave:** o Trio pede uma só vez uma chave gratuita, uma senha longa de uma empresa de IA (um minuto, sem cartão). Funciona com qualquer chave gratuita — ou várias — nesta ordem:
- **console.groq.com/keys** → Create API Key (começa com `gsk_`; sem SMS, com sua conta Google);
- **aistudio.google.com/apikey** → Create API key (Gemini, começa com `AIza`; sem SMS);
- **build.nvidia.com/settings/api-keys** → Generate API Key (a mais forte; pede um código por SMS, começa com `nvapi-`);
- **openrouter.ai/keys** → Create key (dezenas de modelos gratuitos de empresas diferentes, começa com `sk-or-`).

Uma basta; com mais, o Trio quase nunca fica mudo. Sua própria chave paga (`xai-`, `sk-ant-`, `sk-`) também serve.

Rode o Trio e cole a(s) chave(s) quando ele pedir — várias, cada uma numa linha nova. Elas ficam em
iCloud Drive → Shortcuts → `poly-key.txt`, não dentro do atalho. Na primeira execução o iPhone pede
permissão 4–6 vezes: toque em **Sempre Permitir** toda vez, na hora.

O Trio tenta todas as chaves com todos os modelos gratuitos até um responder; só se todos falharem
ele diz o que cada um respondeu (sem saldo, limite, sobrecarregado, chave inválida) e o que fazer.
Para adicionar uma chave depois, cole-a numa linha nova do `poly-key.txt` ou apague o arquivo e rode o Trio.

## Sobre o iCloud — nenhum plano pago é necessário

O Duo não exige iCloud pago. O fluxo principal (pergunta → as duas IAs → resposta na tela e na área de transferência) nunca encosta no iCloud. Só duas conveniências opcionais o usam: o diário das execuções e o arquivo de imagem — ambos medidos em kilobytes, e os 5 GB gratuitos de qualquer ID Apple cobrem décadas disso. Se o iCloud Drive estiver desligado ou cheio, a resposta ainda chega à sua tela e à sua área de transferência (isso é garantido por desenho) — só a entrada no diário é pulada. Não quer diário nenhum? Veja Privacidade, abaixo.

## Privacidade

O `Duo-journal.md` guarda toda pergunta e toda resposta em texto puro no iCloud Drive. Não quer o histórico? Apague a ação de diário no editor do atalho. Para apagar o que já existe, exclua o arquivo `Duo-journal.md` no Arquivos. Se o diário crescer demais, é só renomear o arquivo (por exemplo, para `Duo-journal-agosto.md`) — um novo é criado automaticamente na execução seguinte.

## Se algo der errado

- **"Ask Claude" não aparece na lista de ações:** atualize o app do Claude e o iOS (iOS 18 ou posterior).
- **Resposta vazia:** abra uma vez os apps do ChatGPT e do Claude e rode o atalho de novo.
- **O pedido de permissão sumiu antes de você tocar:** rode o atalho de novo e toque em **Always Allow** na hora.
- **O ChatGPT diz "You are logged out"** (com você claramente logado) — abra o app do ChatGPT, feche-o e rode o Duo de novo. Uma falha conhecida que sempre se resolve assim.
- **O Claude diz "This model isn't available right now"** — acabou o limite diário do Claude gratuito ou o modelo escolhido no app do Claude não está no seu plano. Escolha o Sonnet no app do Claude ou espere o limite reiniciar; enquanto isso, o Trio confere com uma IA gratuita com chave.
- **O Claude fica em silêncio / resposta vazia em uma pergunta longa** — a ação do Claude tem um limite de tempo: ela pode devolver o controle antes de o Claude terminar, enquanto ele continua escrevendo a resposta dentro do próprio app. Abra o Claude, a resposta está lá — copie com o botão do próprio app. Para a próxima vez: uma pergunta mais curta volta com mais confiabilidade. Se simplesmente falhou de vez, tire o Atalhos dos apps recentes e execute de novo.
- **Compartilhar o Duo com alguém:** mande o `Duo.shortcut` como arquivo solto, sem zipar (um zip no telefone significa passos extras). No Telegram: mantenha o dedo no arquivo → Compartilhar/Salvar em Arquivos, e não um toque simples.
- **Não renomeie o atalho Duo.** A Siri ("E aí Siri, Duo") e o botão "🔁 Outro modo" o encontram pelo nome exato "Duo". Renomeie-o (ou reimporte e acabe com um "Duo 1") e esses caminhos param de funcionar em silêncio. Se surgir uma duplicata na reinstalação, apague o atalho antigo e mantenha exatamente um chamado "Duo". (Exceção: os complementos compilados a partir do código-fonte procuram "Poly" — veja os complementos acima.)
- **Respostas mais fracas do que o esperado** — a ação usa o modelo que estiver definido como padrão no app do Claude: abra o Claude, troque o modelo, feche o app e rode o Duo de novo. Bom hábito: conferir o modelo no cabeçalho do Claude antes de uma execução importante.
- **Um compartilhamento trouxe só um link e nada aconteceu** — as ações não baixam páginas da web sozinhas: abra a página, selecione uma parte do texto e compartilhe esse texto.
- **Bônus:** a resposta final também vai para a área de transferência compartilhada (Área de Transferência Universal) — em um Mac ou iPad você cola com Cmd+V sem tocar no telefone.
- **Depois de uma atualização grande do iOS** (digamos, para o iOS 27), faça uma Crítica de teste. Uma atualização grande do Atalhos pode pedir as permissões de novo ou mostrar um cartão "Concluído" a mais — uma execução resolve isso.
- O custo em mensagens sai das suas **assinaturas** de cada serviço (não é API), dividindo os mesmos limites das suas conversas normais. O modelo usado é o que estiver definido como padrão em cada app.

## O que vem depois da resposta final

Abaixo da tela final, o Duo pergunta: **"✅ Pronto"** ou **"🔁 Outro modo — mesma pergunta"**. A segunda opção reinicia o Duo com a sua pergunta já preenchida (você pode editá-la) e deixa você escolher outro modo. Prático para rodar a Crítica e, logo em seguida, o Mapa de divergências na mesma pergunta, sem redigitar nada.

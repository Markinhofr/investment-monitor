# Produção v2 — plano de transição controlada

Estado: **preparado, não executado**. main e configurações de Pages/agendamento permanecem inalteradas. O plano publica um dashboard de monitorização **sem fair values nem sinais de compra**. A aprovação de publicação não aprova a avaliação financeira.

## Estado confirmado e estratégia

Há um único workflow de monitorização registado: ID **412557026**, caminho `.github/workflows/monitor.yml`. main continua a branch predefinida; Pages está em modo legacy, fonte main:/docs. O cron atual pertence à versão existente em main e continua ativo até à transição autorizada.

Recomendação: manter main como branch predefinida e substituir o workflow no **mesmo caminho**, mediante merge aprovado do PR #1. O workflow da v2 recolhe/testa o código de investment-v2 e grava apenas nessa branch. Em main ficam o disparador aprovado e o código revisto pelo merge; não haverá commits automáticos de dados em main. Não criar um segundo workflow cron, automação externa ou mudar a branch predefinida.

Pages passará a modo **GitHub Actions (`build_type: workflow`)**, com upload/deploy explícito do diretório docs validado. A simples mudança de Pages para investment-v2:/docs não é suficiente como estratégia: pushes feitos com GITHUB_TOKEN não desencadeiam recursivamente todos os workflows de publicação. O deploy explícito elimina essa dependência. Usa as ações oficiais upload-pages-artifact@v4 e deploy-pages@v4.

O environment github-pages atualmente permite apenas main. O job de deploy exige main e mantém essa proteção. Uma execução manual de teste antes do merge, em investment-v2, não publica o site. Depois da aprovação/merge, a primeira publicação é disparada a partir de main, mas testa/recolhe e atualiza os dados de investment-v2.

Três variáveis de repositório controlam a ativação; ausentes equivalem a desligado:

| Variável | Efeito |
| --- | --- |
| MONITOR_AUTOMATION_ENABLED | Permite execução agendada da v2; manual continua disponível. |
| PAGES_DEPLOY_ENABLED | Permite upload de artefacto e deploy a partir de main. |
| MONITOR_NOTIFICATIONS_ENABLED | Permite Telegram no workflow; não altera os Secrets. |

A exclusão mútua `investment-v2-monitor`, com cancel-in-progress false, serializa execuções da v2. **Não basta para excluir a v1**: a migração inclui desativar o workflow antigo e esvaziar execuções antes de qualquer teste/publicação v2.

## Preparação já automatizada

`python scripts/production_preflight.py` é somente leitura: confirma branch, PR/SHA, default branch/SHA, Pages, workflow único e execuções ativas, e exige política financeira desligada e revisão não aprovada. Não lê Secrets, faz merge, altera Settings, envia mensagens ou dispara workflows. Executá-lo novamente imediatamente antes da transição.

O workflow testa a revisão de investment-v2 e transporta o SHA para o job de atualização. Se a branch mudar entre teste e execução, aborta em vez de executar código diferente. PRs executam apenas testes. `python scripts/check_dashboard.py` rejeita artefactos com fair values/margens enquanto a política está bloqueada. `docs/release.json` identifica versão, revisão de código, data e estado financeiro publicados.

## Sequência a executar por Codex após uma única aprovação explícita do proprietário

1. Registar os SHAs do PR e de main, configuração Pages e variáveis existentes. Confirmar PR aberto/integrável, testes verdes da revisão final e bloqueio financeiro ativo. Se os SHAs mudarem, rever o delta antes de prosseguir.
2. Guardar MONITOR_AUTOMATION_ENABLED=false, PAGES_DEPLOY_ENABLED=false e MONITOR_NOTIFICATIONS_ENABLED=false. Desativar o workflow ID 412557026 e confirmar o estado disabled_manually. Cancelar execuções antigas em fila e aguardar que as já iniciadas terminem (ou cancelá-las com controlo). Confirmar **zero** execuções ativas/pendentes da monitorização e da publicação legacy antes do passo seguinte. Desativar o workflow não cancela execuções já iniciadas.
3. Fazer merge do PR #1 para main com o SHA revisto como condição (`sha` na API de merge), preservando investment-v2. Este é o passo que requer a aprovação do proprietário; **não foi executado**. Não ativar auto-merge e não eliminar a branch de dados/código investment-v2.
4. Alterar Pages de legacy para workflow. Manter a restrição do environment github-pages a main e verificar que não foi criado um segundo workflow de publicação/cron. Ativar PAGES_DEPLOY_ENABLED=true, mantendo automação e notificações desligadas.
5. Reativar o **mesmo workflow ID** e fazer uma única execução manual, `mode=daily`, `--ref main`. A automação permanece desligada. A execução deverá passar testes, recolher SEC/preços, validar o artefacto, gravar dados só em investment-v2 e fazer deploy Pages. Qualquer erro interrompe a transição; não ativar o cron.
6. Verificar a URL pública por HTTP: `release.json` tem version=2.0, source_commit igual ao SHA efetivamente testado e data da execução; latest.json e dcf_alphabet.json mostram avaliação bloqueada, sem valores/margens; HTML mostra atualização, cotações, histórico e bloqueios. Verificar o deploy/environment e abrir dashboard/DCF em desktop e móvel. Não confiar só no commit ou no sucesso do upload. Pode haver propagação/cache do Pages.
7. Ativar MONITOR_NOTIFICATIONS_ENABLED=true e fazer uma única execução manual de confirmação. Verificar entrega ou supressão justificada pelo estado persistido; não apagar notification_state para forçar uma mensagem. Confirmar ausência de mensagens repetidas. Se existirem alertas relevantes, podem ser enviados neste teste autorizado de produção.
8. Só depois ativar MONITOR_AUTOMATION_ENABLED=true. Conferir que há **um único** workflow cron e nenhuma automação externa adicional. Confirmar a primeira execução diária das 22:30 de Lisboa e o resumo semanal de domingo às 10:30. Registar IDs e o deploy final. GitHub pode atrasar cron; uma execução fora da janela pode ser perdida e pode exigir disparo manual.

A aprovação necessária é: **autorizar a integração do PR #1 e esta transição de publicação/agendamento, mantendo a avaliação financeira bloqueada**. Codex pode executar toda a sequência; o proprietário não precisa de copiar código, introduzir novamente Secrets ou editar ficheiros manualmente. Se forem alterados o PR ou a configuração, rever os factos novos antes da transição.

## Rollback

Se algo falhar antes de publicar: manter automação/notificações desligadas e o site anterior intacto; corrigir na investment-v2 e repetir o teste, sem iniciar um segundo agendamento.

Se falhar após publicação: desligar primeiro automação/notificações e desativar o workflow; aguardar/cancelar execuções ativas. Pode restaurar-se Pages para legacy main:/docs usando a configuração guardada (o site daí refletirá o conteúdo que então estiver em main). Isso não garante recuperar exatamente a v1 se o merge já ocorreu. Para recuperar exatamente a versão anterior, preparar em investment-v2 um artefacto com os docs do SHA anterior guardado e publicá-lo explicitamente por um job aprovado a partir de main; não reescrever a história nem fazer um segundo merge/revert em main sem nova autorização. Não restaurar o cron antigo enquanto o novo puder executar. Se o workflow só for desativado, o último site publicado permanece acessível, mas desatualizado; verificar o resultado público.

## Decisões financeiras independentes

Consultar [ALPHABET_AUDIT.md](ALPHABET_AUDIT.md). Não é necessário resolver as decisões financeiras para publicar monitorização. Para mostrar fair values mais tarde faltam: escolher FCFF/FCFE e desconto, implementar preferenciais/diluição e locações, definir tratamento dos investimentos/SBC, aprovar uma ponte de FCF normalizado e fundamentar os cenários. Só depois atualizar a revisão vinculada à entrega SEC, efetuar testes de regressão e autorizar explicitamente o desbloqueio da política. Um checkbox não substitui as funcionalidades que o modelo ainda não suporta.

## Referências operacionais

- [GitHub Pages — workflows personalizados](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub — eventos disparados por GITHUB_TOKEN](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)

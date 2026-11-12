# NPS clínico: tamanho e homogeneidade das ROIs

## Decisões apoiadas pela literatura

1. **Não há um tamanho universal de ROI.** O aumento da ROI melhora a resolução em frequência, mas reduz o número de amostras independentes e aumenta a chance de violar a estacionariedade local. Dolly et al. compararam 32, 64 e 128 px e concluíram que o menor tamanho deve respeitar a amostragem radial desejada; no experimento deles, 32 px foi o mínimo adequado.
2. **16×16 não deve ser a análise principal convencional.** ROIs pequenas ficam mais dependentes do método de remoção do fundo e da janela, sobretudo nas baixas frequências. O resultado de 16×16 é mantido como baseline para verificar se a conclusão anterior é reproduzida.
3. **64×64 tem precedente clínico, mas pode não caber no tórax.** Smith et al. estimaram NPS *in vivo* no fígado com blocos não sobrepostos de 64×64 px, detrending por polinômio 2D de segunda ordem e uma máscara de uniformidade calculada em vizinhanças de 9×9 px.
4. **A AAPM usa 64×64 como referência em phantom, não como regra para imagens clínicas.** O TG-233 recomenda cerca de 100 ROIs de 64×64 no centro de imagens de phantom e alerta que ROIs grandes podem não ser estacionárias e que regiões com estruturas/artefatos devem ser evitadas.
5. **O tamanho da ROI muda o NPS medido.** Estudos específicos de dependência de ROI testaram tamanhos de 8 a 256 px e observaram dependência do resultado com o tamanho pelo método convencional. Portanto, a análise de sensibilidade é parte do resultado, não apenas uma escolha de implementação.

## Protocolo do estudo com ROIs quadradas

- Região: tecido mole liso fora do pulmão, osso, pele e bordas.
- Tamanhos auditados: 16, 24, 32, 48 e 64 px.
- Principal exploratória neste dataset: 24×24 com threshold permissivo, por ser a maior configuração que inclui os três pacientes.
- Baseline: 16×16 sem threshold adicional.
- Sensibilidade metodológica: 32×32 com threshold moderado; demais tamanhos e thresholds permanecem na auditoria.
- Escore de estrutura: RMS do gradiente após suavização gaussiana, normalizado pela faixa robusta da imagem real.
- Thresholds: percentis 25, 50 e 75 dos escores candidatos agregados das CTs reais. Eles são calibrados uma única vez e nunca nas imagens sintéticas.
- Pareamento: as mesmas coordenadas da CT real são aplicadas a DSR, Baseline e GPBO-11.
- Agregação: comparação pareada dentro de cada corte; mediana dos cortes por paciente; mediana dos pacientes na coorte. Espectros de cortes distintos não são concatenados.
- Unidade provisória: ciclos/pixel. A conversão para ciclos/mm será feita quando `PixelSpacing` estiver disponível.

O threshold não usa o desvio-padrão bruto da ROI. Isso evita rejeitar automaticamente uma região apenas porque seu ruído é maior, o que enviesaria a comparação de magnitude.

A escolha de 24×24 é uma decisão de cobertura específica deste conjunto, não uma recomendação universal de NPS. A configuração 32×32 continua metodologicamente preferível para resolução em frequência, mas aqui possui cobertura insuficiente da coorte. Quando volumes completos e DICOMs estiverem disponíveis, 32×32 deve ser reavaliada por série e condição de aquisição.

## Referências

- Dolly S, Chen H-C, Anastasio M, Mutic S, Li H. *Practical considerations for noise power spectra estimation for clinical CT scanners*. J Appl Clin Med Phys. 2016;17(3):392–407. doi:10.1120/jacmp.v17i3.5841.
- Smith TB, Abadi E, Sauer TJ, et al. *Development and validation of an automated methodology to assess perceptual in vivo noise texture in liver CT*. J Med Imaging. 2021;8(5):052113. doi:10.1117/1.JMI.8.5.052113.
- Samei E, Bakalyar D, Boedeker KL, et al. *AAPM Report No. 233: Performance Evaluation of Computed Tomography Systems*. AAPM; 2019.
- Ichikawa K, et al. *Method for measuring noise-power spectrum independent of the effect of extracting the region of interest from a noise image*. Radiol Phys Technol. 2023. PMID: 37515623.

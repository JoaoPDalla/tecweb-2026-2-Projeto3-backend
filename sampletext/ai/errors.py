class ErroIA(Exception):
    def __init__(self, codigo, mensagem, status=502):
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status = status

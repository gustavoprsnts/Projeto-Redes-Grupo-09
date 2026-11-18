import hashlib
import re
import unicodedata

class Hangman:
    #funcao que inicializa o jogo com a palavra a ser adivinhada, o número de vidas e o estado do jogo
    def __init__(self, palavra: str, vidas: int = 6):
        self.palavra = self.normaliza_palavra(palavra)
        self.vidas = vidas
        self.letras_tentadas: set[str] = set()
        self.letras_erradas: list[str] = []
        self.estado = "RUNNING"

    @staticmethod
    def normaliza_palavra(palavra: str) -> str:

        #remove os espaços em branco e padroniza em minuscula
        palavra = palavra.strip().lower()

        #separa os acentos
        palavra_nfkd = unicodedata.normalize("NFKD", palavra)

        #remove os acentos
        palavra_normalizada = "".join([caractere for caractere in palavra_nfkd if not unicodedata.combining(caractere)])

        if len(palavra_normalizada) >= 3 and len(palavra_normalizada)<=20:
            if bool(re.fullmatch(r"[a-z]+", palavra_normalizada)):
                return palavra_normalizada


        raise ValueError("Palavra inválida!")

    #funcao que processa o palpite de uma letra, atualiza o estado do jogo e retorna um dicionário com o resultado do palpite
    def palpite(self, letra: str) -> dict:
        if self.estado != "RUNNING":
            return {"accepted": False, "reason": "game_not_running"}

        letra = letra.lower().strip()

        if not re.fullmatch(r"[a-z]", letra):
            return {"accepted": False, "reason": "invalid_letter"}
        
        if letra in self.letras_tentadas:
            return {"accepted": False, "reason": "letter_already_used"}
        
        self.letras_tentadas.add(letra)

        correto = letra in self.palavra
        if not correto:
            self.letras_erradas.append(letra)
            self.vidas = max(0, self.vidas - 1)

        self.verifica_estado()
        return {
            "accepted": True,
            "correct": correto,
            "status": self.estado,
        }
        
    #funcao que retorna a palavra com as letras acertadas e as letras não acertadas substituidas por "_"
    def mascara(self) -> str:
        mascara = ""
        for letra in self.palavra:
            if letra in self.letras_tentadas:
                mascara += letra
            else:
                mascara += "_"

        return mascara
    #funcao que processa o palpite de uma palavra inteira
    def tentar_palavra(self, palpite_palavra: str) -> dict:
        if self.estado != "RUNNING":
            return {"accepted": False, "reason": "game_not_running"}

        try:
            palpite_palavra = self.normaliza_palavra(palpite_palavra)
        except ValueError:
            return {"accepted": False, "reason": "invalid_word"}

        if palpite_palavra == self.palavra:
            self.letras_tentadas.update(self.palavra)
            self.estado = "WON"
            return {
                "accepted": True,
                "correct": True,
                "status": self.estado,
            }

        self.vidas = max(0, self.vidas - 1)
        self.verifica_estado()
        return {
            "accepted": True,
            "correct": False,
            "status": self.estado,
        }
    #funcao que retorna o hash da palavra para ser usado na comunicação entre peers
    def word_hash(self) -> str:
        return hashlib.sha256(self.palavra.encode("utf-8")).hexdigest()

    #funcao que verifica se o jogo foi vencido, perdido ou ainda está em andamento
    def verifica_estado(self) -> str:
        if self.mascara() == self.palavra:
            self.estado = "WON"

        elif self.vidas <= 0:
            self.estado = "LOST"

        return self.estado

    #retorna um dicionario com o estado atual do jogo, incluindo a palavra mascarada, as letras erradas, o número de vidas restantes e o status do jogo
    def snapshot(self) -> dict:
        return{
            "masked": self.mascara(),
            "wrong_letters": self.letras_erradas.copy(),
            "lives": self.vidas,
            "status": self.estado,          
        }
            
        


    
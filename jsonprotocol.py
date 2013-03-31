from twisted.internet import reactor, protocol
from twisted.internet.endpoints import TCP4ServerEndpoint
import StringIO


class JSONAccumulator():
    """
    This is not a json parser.  The purpose of this naive collector
    is to enable a delimitless protocol that will recieve JSON string
    over a network and has to determine when the json string is complete
    Current known limitations:
    -- Will not process escaped charachters
    """
    ctrl_char = ['"', '[', ']', '{', '}']
    closing_char = {
        ']': '[',
        '}': '{',
        '"': '"'
        }
    class status():
        current_status = 0
        error_str = ""
        MORE_DATA = "MORE_DATA"
        COMPLETE = "COMPLETE"
        ERROR = "ERROR"

    def __init__(self):
        self.reinit()

    def reinit(self):
        self.char_buffer = StringIO.StringIO()
        self.ctrl_stack = []
        self.in_string = False
        self.data_ptr = -1

    def process_data(self, data):
        for char in data:
            self.char_buffer.write(char)
            self.data_ptr += 1

            # JSON structures should only start with [ or {
            if len(self.ctrl_stack) == 0 and char != '[' and char != '{':
                self.status.current_status = self.status.ERROR
                self.status.error_str = "Must start with { or ["
                self.reinit()
                # return here do not place more char in the buffer
                yield {'STATUS': self.status.current_status, 'ERROR_STR': self.status.error_str}
                
            elif char == '"':
                if self.in_string == True and self.ctrl_stack[-1] == '"':
                    # we've matched a string
                    self.ctrl_stack.pop()
                    self.in_string = False
                else:
                    # We're in a string
                    self.ctrl_stack.append(char)
                    self.in_string = True
                    
            elif self.in_string == False and char == '[' or char == '{':
                self.ctrl_stack.append(char)
            elif self.in_string == False and char == ']' or char == '}':
                # do somethign when control_stack is 0
                if len(self.ctrl_stack) and self.ctrl_stack[-1] == self.closing_char[char]:
                    self.ctrl_stack.pop()
                else:
                    # some sort of parsing error
                    self.status.current_status = self.status.ERROR
                    self.status.error_str = "Unmatched closing control '{char}'".format(char=char)
                    self.reinit()
                    # return here do not place more char in the buffer
                    yield {'STATUS': self.status.current_status, 'ERROR_STR': self.status.error_str}
            if len(self.ctrl_stack) == 0:
                # we've assmebled a json structure
                self.status.current_status = self.status.COMPLETE
                self.status.error_str = ""
                assembled_json = self.char_buffer.getvalue()
                self.reinit()
                yield {'STATUS': self.status.current_status,
                        'ERROR_STR': self.status.error_str,
                        'JSON': assembled_json}

        self.status.current_status = self.status.MORE_DATA
        self.status.error_str = ""
        yield {'STATUS': self.status.current_status,
               'ERROR_STR': self.status.error_str}
        return

class JSONProtocol(protocol.Protocol):
    def __init__(self):
        self.json_accumulator = JSONAccumulator()
        
    def dataReceived(self, data):
        char_processor = self.json_accumulator.process_data(data)
        try:
            for yvalue in char_processor:
                if yvalue['STATUS'] == JSONAccumulator.status.ERROR:
                    self.transport.write(str(yvalue) + "\n")
                if yvalue['STATUS'] == JSONAccumulator.status.COMPLETE:
                    self.transport.write(str(yvalue) +  "\n")
        except StopIteration:
            pass

class JSONFactory(protocol.ServerFactory):
    protocol = JSONProtocol


def main():
    reactor.listenTCP(8000, JSONFactory())
    reactor.run()


if __name__ == '__main__':
    main()

def print_exception_stack(e: Exception, context: str = ""):
    '''打印异常堆栈，并可以附加上下文信息'''
    import traceback
    print(f"在{context}过程中发生异常: {e}")
    traceback.print_exc()
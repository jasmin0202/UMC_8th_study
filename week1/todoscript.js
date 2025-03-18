function addTodo() {
    let input = document.getElementById("todo-input");
    let todoList = document.getElementById("todo-items");

    if (input.value.trim() !== "") {
        let li = document.createElement("li");
        li.innerHTML = `${input.value}
            <button class = "done-btn" onclick="completeTodo(this)">완료</button>`;

            todoList.appendChild(li);
            input.value=""; // 입력창 초기화화
    }
}

function completeTodo (button) {
    let donelist = document.getElementById("done-list");
    let li= button.parentElement;
    li.removeChild(button);

    donelist.appendChild(li);
}

function removeTodo(button) {
    let li=button.parentElement;
    li.remove();
}
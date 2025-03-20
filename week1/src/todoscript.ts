function addTodo(): void {
    const input = document.getElementById("todo-input") as HTMLInputElement;
    const todoList = document.getElementById("todo-list") as HTMLUListElement;

    if (input.value.trim() !== "") {
        const li = document.createElement("li");
        li.classList.add("list");
        li.innerHTML = `${input.value} `;

        // 완료 버튼 생성
        const completeButton = document.createElement("button");
        completeButton.classList.add("greenbutton");
        completeButton.innerText = "완료";

        // 완료 버튼 클릭 시 completeTodo 실행
        completeButton.addEventListener("click", () => completeTodo(li)); // 익명 함수를 사용

        li.appendChild(completeButton);
        todoList.appendChild(li);

        // 입력창 초기화
        input.value = "";
    }
}

function completeTodo(li: HTMLLIElement): void {
    const donelist = document.getElementById("done-list") as HTMLUListElement;

    // 완료 버튼 제거
    const completeButton = li.querySelector(".greenbutton");
    if (completeButton) {
        li.removeChild(completeButton);
    }

    // 삭제 버튼 추가
    const deleteButton = document.createElement("button");
    deleteButton.classList.add("redbutton");
    deleteButton.innerText = "삭제";

    // 삭제 버튼 클릭 시 removeTodo 실행
    deleteButton.addEventListener("click", () => removeTodo(li));

    li.appendChild(deleteButton);
    donelist.appendChild(li);
}

function removeTodo(li: HTMLLIElement): void {
    li.remove();
}
